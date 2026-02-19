import os
import subprocess
from typing import List, Union

import xarray as xr

from bluemath_tk.wrappers._base_wrappers import BaseModelWrapper

class OpenFoamWrapper(BaseModelWrapper):

    default_parameters = {
        "preprocess_script": {
            "type": str,
            "value": None,
            "description": "Bash script for preprocessing case files."},
        "postprocess_script": {
            "type": str,
            "value": None,
            "description": "Bash script for preprocessing case files."},        
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
        
    def build_case(self, case_context: dict, case_dir: str) -> None:
        
        os.makedirs(os.path.join(case_dir,'0'), exist_ok=True)
        os.makedirs(os.path.join(case_dir,'constant','polyMesh'), exist_ok=True)
        os.makedirs(os.path.join(case_dir,'system'), exist_ok=True)

    def build_case_and_render_files(self, case_context: str, case_dir: str) -> None:
        super().build_case_and_render_files(case_context=case_context, case_dir=case_dir)

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

    def postprocess_case(
        self,
        case_num: int,
        case_dir: str,
        case_context: dict,
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

        Returns
        -------
        xr.Dataset
            The postprocessed Dataset.
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

            self.logger.warning(
        #if op.exists(output_postprocessed_file_path):
                "Output postprocessed file already exists. Skipping postprocessing."
            )
            return xr.open_dataset(output_postprocessed_file_path)

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


