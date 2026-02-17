import os
import subprocess

from bluemath_tk.wrappers._base_wrappers import BaseModelWrapper

class OpenFoamWrapper(BaseModelWrapper):

    default_parameters = {
        "preprocess_script": {
            "type": str,
            "value": 'Hello',
            "description": "Bash script for preprocessing case files.",
        }}

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



