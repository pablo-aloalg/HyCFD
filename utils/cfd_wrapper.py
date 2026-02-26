import os
import os.path as op
import re
import subprocess
import copy
from typing import List, Union
import math
import numpy as np
import xarray as xr
import pandas as pd
from collections import deque
from bluemath_tk.wrappers._base_wrappers import BaseModelWrapper

import sys
sys.path.append(os.path.dirname(__file__))
from utils.cfd_functions_pre import read_boundary_patches, write_openfoam_field
from utils.cfd_functions_post import readWaveGauge, get_waveparams_from_gauge

class OpenFoamWrapper(BaseModelWrapper):

    default_parameters = {
        "points_per_wavelenght": {
            "type": int,
            "value": None,
            "description": "Bash script for preprocessing case files."},        
        "preprocess_script": {
            "type": str,
            "value": None,
            "description": "Bash script for preprocessing case files."},
        "postprocess_script": {
            "type": str,
            "value": None,
            "description": "Bash script for preprocessing case files."},        
        }

    available_launchers = {
        "mpi": "bash /home/alonsoap_foam/OpenFOAM/alonsoap_foam-v1912/run/HyCFD/inputs/scripts_openfoam/run_case.sh /case_dir",
        "mpi_continuerun": "bash /home/alonsoap_foam/OpenFOAM/alonsoap_foam-v1912/run/HyCFD/inputs/scripts_openfoam/continue_run_case.sh /case_dir",
    }

    postprocess_functions = {
        "wave_gauges": "surfaceElevationAnyName",
    }

    def __init__(
        self,
        templates_dir: str,
        metamodel_parameters: dict,
        fixed_parameters: dict,
        output_dir: str,
        templates_name: dict = "all",
        debug: bool = True,
    ) -> None:
        """
        Initialize the openFOAM model wrapper.
        """

        super().__init__(
            templates_dir=templates_dir,
            metamodel_parameters=metamodel_parameters,
            fixed_parameters=fixed_parameters,
            output_dir=output_dir,
            templates_name=templates_name,
            default_parameters=self.default_parameters,
        )

        self.set_logger_name(
            name=self.__class__.__name__, level="DEBUG" if debug else "INFO"
        )

    def list_available_postprocess_functions(self) -> List[str]:
        """
        List available postprocess functions.

        Returns
        -------
        List[str]
            The available postprocess functions.
        """

        return list(self.postprocess_functions.keys())
        
    def check_last_lines(self, filename):
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            last_lines = deque(f, maxlen=10)

        normalized = [line.strip() for line in last_lines]

        if any("End" in line for line in normalized) and any("Finalising parallel run" in line for line in normalized):
            return "Completed"
        elif any("End of error message" in line for line in normalized):
            return "Error"
        else:
            return "Running"

    def rescale_mesh_ppw(self, ppw, wavelength, input_file, output_file):
        with open(input_file, "r") as f:
            text = f.read()
        
        dx_target = wavelength / ppw

        vertices_block = re.search(r'vertices\s*\((.*?)\);', text, re.S).group(1)
        vertex_lines = re.findall(r'\((.*?)\)', vertices_block)

        vertices = []
        for v in vertex_lines:
            x, y, z = map(float, v.split())
            vertices.append((x, y, z))

        blocks_block = re.search(r'blocks\s*\((.*?)\);', text, re.S).group(1)
        block_lines = re.findall(r'hex\s*\((.*?)\)\s*\((.*?)\)\s*simpleGrading\s*\((.*?)\)', blocks_block)

        new_blocks = []

        for verts, cells, grading in block_lines:
            vert_ids = list(map(int, verts.split()))
            nx_old, ny_old, nz_old = map(int, cells.split())

            v0 = vertices[vert_ids[0]]
            v1 = vertices[vert_ids[1]]

            Lx = abs(v1[0] - v0[0])

            nx_new = max(1, round(Lx / dx_target))

            new_blocks.append((vert_ids, nx_new, ny_old, nz_old, grading))

        new_blocks_text = "blocks\n(\n"

        for verts, nx, ny, nz, grading in new_blocks:
            vert_string = " ".join(map(str, verts))
            new_blocks_text += f"    hex ({vert_string}) ({nx} {ny} {nz}) simpleGrading ({grading})\n"

        new_blocks_text += ");"

        text_new = re.sub(r'blocks\s*\(.*?\);', new_blocks_text, text, flags=re.S)
        
        with open(output_file, "w") as f:
            f.write(text_new)

    def get_n_cells(self, case_dir: str) -> int:
        """
        Return the number of cells in an OpenFOAM mesh.
        
        It reads the 'owner' file in constant/polyMesh and extracts nCells from the header.
        
        Parameters
        ----------
        case_dir : str
            Path to the OpenFOAM case directory.
        
        Returns
        -------
        int
            Number of cells in the mesh.
        """
        owner_file = os.path.join(case_dir, "constant", "polyMesh", "owner")
        
        if not os.path.isfile(owner_file):
            raise FileNotFoundError(f"'owner' file not found at {owner_file}")
        
        with open(owner_file, "r") as f:
            for line in f:
                # Look for the line containing nCells in the header
                if "note" in line and "nCells" in line:
                    match = re.search(r"nCells\s*:\s*(\d+)", line)
                    if match:
                        return int(match.group(1))
        
        raise ValueError("Could not find nCells in the owner file header.")

    def rewrite_boundary_cond(self, case_context: str, case_dir: str) -> None:

        boundary_file = case_context['boundary_file']
        patches = read_boundary_patches(boundary_file)

        alpha_inlet_patch_vals = case_context['alpha_inlet_patch_vals']
        
        Ncells = self.get_n_cells(case_dir)
        Uvec = np.zeros((Ncells, 3))
        p_rgh_vec = np.zeros(Ncells)
        alphaCol = np.zeros(Ncells) 

        write_openfoam_field(
            output_file=op.join(case_dir,"0","U"),
            class_name="volVectorField",
            dims=[0, 1, -1, 0, 0, 0, 0],
            internal_data=Uvec,
            patches=patches,
            field_name="U",
            location="0",
            alpha_inlet_patch_vals=alpha_inlet_patch_vals,
        )

        write_openfoam_field(
            output_file=op.join(case_dir,"0","p_rgh"),
            class_name="volScalarField",
            dims=[1, -1, -2, 0, 0, 0, 0],
            internal_data=p_rgh_vec,
            patches=patches,
            field_name="p_rgh",
            location="0",
            alpha_inlet_patch_vals=alpha_inlet_patch_vals,
        )

        write_openfoam_field(
            output_file=op.join(case_dir,"0","alpha.water"),
            class_name="volScalarField",
            dims=[0, 0, 0, 0, 0, 0, 0],
            internal_data=alphaCol,
            patches=patches,
            field_name="alpha.water",
            location="0",
            force_nonuniform=True,
            alpha_inlet_patch_vals=alpha_inlet_patch_vals,
        )

    def build_case(self, case_context: dict, case_dir: str) -> None:
        os.makedirs(os.path.join(case_dir,'0'), exist_ok=True)
        os.makedirs(os.path.join(case_dir,'constant','polyMesh'), exist_ok=True)
        os.makedirs(os.path.join(case_dir,'system'), exist_ok=True)

    def build_case_and_render_files(self, case_context: str, case_dir: str) -> None:
        super().build_case_and_render_files(case_context=case_context, case_dir=case_dir)

        if case_context['points_per_wavelenght'] is not None:
            ppw = case_context['points_per_wavelenght']

            input_base_path  = case_context['block_mesh_dict']
            output_mesh_path = os.path.join(case_dir,'constant','polyMesh','blockMeshDict')

            wavelength = 9.81 * ( (case_context['tp']) ** 2 ) / (2 * math.pi)

            self.rescale_mesh_ppw(ppw=ppw, wavelength=wavelength, input_file=input_base_path, output_file=output_mesh_path)
        

        if case_context['createmesh_script'] is not None:
            script_path = case_context['createmesh_script']
            arg1 = case_dir
            log_file_path = f"logs/cases_openfoam/{case_context['case_num']:04d}_createmesh.log"

            with open(log_file_path, "w") as log_file:

                process = subprocess.Popen(["bash", script_path, arg1], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) #### TODO write stdout and stderr into the log

                for line in process.stdout:
                    log_file.write(line)
                    log_file.flush()

                process.wait()

                log_file.write(f"\nProcess exited with code {process.returncode}\n")

        self.rewrite_boundary_cond(case_context=case_context, case_dir=case_dir)

        if case_context['preprocess_script'] is not None:
            script_path = case_context['preprocess_script']
            arg1 = case_dir
            log_file_path = f"logs/cases_openfoam/{case_context['case_num']:04d}"

            with open(log_file_path, "w") as log_file:

                process = subprocess.Popen(["bash", script_path, arg1], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) #### TODO write stdout and stderr into the log

                for line in process.stdout:
                    log_file.write(line)
                    log_file.flush()

                process.wait()

                log_file.write(f"\nProcess exited with code {process.returncode}\n") 

    def monitor_cases(self, value_counts: str = None) -> Union[pd.DataFrame, dict]:
        """
        Monitor the cases based on different model log files.
        """

        cases_status = {}

        for case_dir in self.cases_dirs:
            case_dir_name = os.path.basename(case_dir)
            if os.path.exists(os.path.join(case_dir, "waveFoam.log")):
                status_case = self.check_last_lines(os.path.join(case_dir, "waveFoam.log"))
                cases_status[case_dir_name] = status_case
            else:
                cases_status[case_dir_name] = "Not Started"

        return super().monitor_cases(
            cases_status=cases_status, value_counts=value_counts
        )

    def postprocess_case(
        self,
        case_num: int,
        case_dir: str,
        case_context: dict,
        output_vars: List[str] = None,
        overwrite_output: bool = True,
        overwrite_output_postprocessed: bool = True,
        remove_tab: bool = False,
        remove_nc: bool = False,
    ) -> None:
        """
        Convert tab output files to netCDF file.

        Parameters
        ----------
        case_num : int
            The case number.
        case_dir : str
            The case directory.
        case_context : dict
            The case context.
        output_vars : list, optional
            The output variables to postprocess. Default is None.
        overwrite_output : bool, optional
            Overwrite the output.nc file. Default is True.
        overwrite_output_postprocessed : bool, optional
            Overwrite the output_postprocessed.nc file. Default is True.
        remove_tab : bool, optional
            Remove the tab files. Default is False.
        remove_nc : bool, optional
            Remove the netCDF file. Default is False.

        """

        import warnings

        warnings.filterwarnings("ignore")

        self.logger.info(f"[{case_num}]: Postprocessing case {case_num} in {case_dir}.")

        if case_context['postprocess_script'] is not None:
            script_path = case_context['postprocess_script']
            arg1 = case_dir
            log_file_path = f"logs/cases_openfoam/{case_context['case_num']:04d}"

            with open(log_file_path, "w") as log_file:

                process = subprocess.Popen(["bash", script_path, arg1], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) #### TODO write stdout and stderr into the log

                for line in process.stdout:
                    log_file.write(line)
                    log_file.flush()

                process.wait()

                log_file.write(f"\nProcess exited with code {process.returncode}\n")

        if output_vars is None:
            self.logger.debug(f"[{case_num}]: Postprocessing all available variables.")
            output_vars = list(self.postprocess_functions.keys())

        for var in output_vars:
            if var == "wave_gauges":
                func_name = self.postprocess_functions[var]

                output_df = readWaveGauge(case_dir=case_dir, func_name=func_name)

                wave_params_df = get_waveparams_from_gauge(output_df, reflevel=case_context['swl'])

                output_postprocessed_file_path = op.join(
                    case_dir, f"{var}_postprocessed.csv"
                )

                wave_params_df.to_csv(output_postprocessed_file_path)
        
        return wave_params_df.to_xarray().expand_dims(case_num=[case_context["case_num"]])

    def postprocess_cases(
        self,
        cases_to_postprocess: List[int] = None,
        write_output_nc: bool = False,
        clean_after: bool = False,
        **kwargs,
    ) -> Union[xr.Dataset, List[xr.Dataset]]:
        """
        Postprocess the model output.
        All extra keyword arguments will be passed to the postprocess_case method.

        Parameters
        ----------
        cases_to_postprocess : List[int], optional
            The list with the cases to postprocess. Default is None.
        write_output_nc : bool, optional
            Write the output postprocessed file. Default is False.
        clean_after : bool, optional
            Clean the cases directories after postprocessing. Default is False.
        **kwargs
            Additional keyword arguments to be passed to the postprocess_case method.

        Returns
        -------
        xr.Dataset or List[xr.Dataset]
            The postprocessed file or the list with the postprocessed files.
        """

        if self.cases_context is None or self.cases_dirs is None:
            raise ValueError(
                "Cases context or cases directories are not set. Please run load_cases() first."
            )

        output_postprocessed_file_path = op.join(
            self.output_dir, "output_postprocessed.nc"
        )

        '''self.logger.warning(
        if op.exists(output_postprocessed_file_path):
                "Output postprocessed file already exists. Skipping postprocessing."
            )
            return xr.open_dataset(output_postprocessed_file_path)'''

        if cases_to_postprocess is not None:
            self.logger.warning(
                f"Cases to postprocess was specified, so just {cases_to_postprocess} will be postprocessed."
            )
            self.logger.warning(
                "Remember you can just use postprocess_case method to postprocess a single case."
            )
            cases_dir_to_postprocess = [
                self.cases_dirs[case] for case in cases_to_postprocess
            ]
            cases_context_to_postprocess = [
                self.cases_context[case] for case in cases_to_postprocess
            ]
        else:
            cases_to_postprocess = list(range(len(self.cases_dirs)))
            cases_dir_to_postprocess = copy.deepcopy(self.cases_dirs)
            cases_context_to_postprocess = copy.deepcopy(self.cases_context)

        postprocessed_files = []
        for case_num, case_dir, case_context in zip(
            cases_to_postprocess, cases_dir_to_postprocess, cases_context_to_postprocess
        ):
            try:
                postprocessed_file = self.postprocess_case(
                    case_num=case_num,
                    case_dir=case_dir,
                    case_context=case_context,
                    **kwargs,
                )
                postprocessed_files.append(postprocessed_file)
            except Exception as e:
                self.logger.error(
                    f"Output not postprocessed for case {case_num}. Error: {e}."
                )

        try:
            output_postprocessed = self.join_postprocessed_files(
                postprocessed_files=postprocessed_files
            )
            if write_output_nc:
                self.logger.info(
                    f"Writing output postprocessed file to {output_postprocessed_file_path}."
                )
                output_postprocessed.to_netcdf(output_postprocessed_file_path)
            if clean_after:
                self.logger.warning("Cleaning up all cases dirs.")
                for case_dir in self.cases_dirs:
                    os.rmdir(case_dir)
                self.logger.info("Clean up completed.")
            return output_postprocessed

        except NotImplementedError as exc:
            self.logger.error(f"Error joining postprocessed files: {exc}")
            return postprocessed_files


    def join_postprocessed_files(
        self, postprocessed_files: List[xr.Dataset]
    ) -> xr.Dataset:
        """
        Join postprocessed files in a single Dataset.

        Parameters
        ----------
        postprocessed_files : list
            The postprocessed files.

        Returns
        -------
        xr.Dataset
            The joined Dataset.
        """

        return xr.concat(postprocessed_files, dim="case_num")