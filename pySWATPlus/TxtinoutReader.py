import subprocess
import shutil
import pathlib
import typing
import logging
from .FileReader import FileReader
from .types import ParamsType
from .utils import _build_line_to_add, _apply_param_change, _validate_params

logger = logging.getLogger(__name__)


class TxtinoutReader:

    '''
    Provide functionality for seamless reading, editing, and writing of
    SWAT+ model files located in the `TxtInOut` folder.
    '''

    RESERVED_PARAMS: typing.Final[list[str]] = ['has_units']
    IGNORED_FILE_PATTERNS: typing.Final[tuple[str, ...]] = tuple(
        f'_{suffix}.{ext}'
        for suffix in ('day', 'mon', 'yr', 'aa')
        for ext in ('txt', 'csv')
    )

    def __init__(
        self,
        path: str | pathlib.Path
    ) -> None:

        '''
        Create a TxtinoutReader instance for accessing SWAT+ model files.

        Args:
            path (str or Path): Path to the `TxtInOut` folder, which must contain
                exactly one SWAT+ executable `.exe` file.

        Raises:
            TypeError: If the path is not a valid string or Path, or if the folder contains
                zero or multiple `.exe` files.
            FileNotFoundError: If the specified folder does not exist.
        '''

        # check if path is a string or a path
        if not isinstance(path, (str, pathlib.Path)):
            raise TypeError("path must be a string or Path object")

        path = pathlib.Path(path).resolve()

        # check if folder exists
        if not path.is_dir():
            raise FileNotFoundError("Folder does not exist")

        # check .exe files in the directory
        exe_list = [file for file in path.iterdir() if file.suffix == ".exe"]

        # raise error on .exe file
        if len(exe_list) != 1:
            raise TypeError("Expected exactly one .exe file in the parent folder, but found none or multiple.")

        # find parent directory
        self.root_folder = path
        self.swat_exe_path = path / exe_list[0]

    def enable_object_in_print_prt(
        self,
        obj: str,
        daily: bool,
        monthly: bool,
        yearly: bool,
        avann: bool
    ) -> None:

        '''
        Update an object in the `print.prt` file by setting its value to `True`.
        If the object does not exist in the file, it will be added at the end.

        Note:
            This input does not provide complete control over `print.prt` outputs.
            Some files are internally linked in the SWAT+ model and may still be
            generated even when disabled.

        Args:
            obj (str): The object name or identifier to update or add.
            daily (bool): If `True`, enable daily frequency output.
            monthly (bool): If `True`, enable monthly frequency output.
            yearly (bool): If `True`, enable yearly frequency output.
            avann (bool): If `True`, enable average annual frequency output.
        '''

        # Time frequency dictionary
        time_dict = {
            'daily': daily,
            'monthly': monthly,
            'yearly': yearly,
            'avann': avann
        }

        for key, val in time_dict.items():
            if not isinstance(val, bool):
                raise TypeError(f'Variable "{key}" for "{obj}" must be a bool value')

        # check if obj is object itself or file
        if pathlib.Path(obj).suffix:
            arg_to_add = obj.rsplit('_', maxsplit=1)[0]
        else:
            arg_to_add = obj

        # read all print_prt file, line by line
        print_prt_path = self.root_folder / 'print.prt'
        new_print_prt = ""
        found = False
        with open(print_prt_path) as file:
            for line in file:
                if not line.startswith(arg_to_add + ' '):  # Line must start exactly with arg_to_add, not a word that starts with arg_to_add
                    new_print_prt += line
                else:
                    # obj already exist, replace it in same position
                    new_print_prt += _build_line_to_add(arg_to_add, daily, monthly, yearly, avann)
                    found = True

        if not found:
            new_print_prt += _build_line_to_add(arg_to_add, daily, monthly, yearly, avann)

        # store new print_prt
        with open(print_prt_path, 'w') as file:
            file.write(new_print_prt)

    def set_begin_and_end_year(
        self,
        begin: int,
        end: int
    ) -> None:

        '''
        Modify the simulation period by updating
        the begin and end years in the `time.sim` file.

        Parameters:
            begin (int): Beginning year of the simulation in YYYY format (e.g., 2010).
            end (int): Ending year of the simulation in YYYY format (e.g., 2016).

        Raises:
            ValueError: If the begin year is greater than or equal to the end year.
        '''

        year_dict = {
            'begin': begin,
            'end': end
        }

        for key, val in year_dict.items():
            if not isinstance(val, int):
                raise TypeError(f'"{key}" year must be an integer value')

        if begin >= end:
            raise ValueError("begin year must be less than end year")

        nth_line = 3

        time_sim_path = self.root_folder / 'time.sim'

        # Open the file in read mode and read its contents
        with open(time_sim_path, 'r') as file:
            lines = file.readlines()

        year_line = lines[nth_line - 1]

        # Split the input string by spaces
        elements = year_line.split()

        # insert years
        elements[1] = str(begin)
        elements[3] = str(end)

        # Reconstruct the result string while maintaining spaces
        result_string = '{: >8} {: >10} {: >10} {: >10} {: >10} \n'.format(*elements)

        lines[nth_line - 1] = result_string

        with open(time_sim_path, 'w') as file:
            file.writelines(lines)

    def set_warmup_year(
        self,
        warmup: int
    ) -> None:

        '''
        Modify the warm-up years in the `time.sim` file.

        Args:
            warmup (int): A positive integer representing the number of years
                the simulation will use for warm-up (e.g., 1).

        Raises:
            ValueError: If the warmup year is less than or equal to 0.
        '''

        if not isinstance(warmup, int):
            raise TypeError('"warmup" must be an integer value')
        if warmup <= 0:
            raise ValueError('"warmup" must be a positive integer')

        time_sim_path = self.root_folder / 'print.prt'

        # Open the file in read mode and read its contents
        with open(time_sim_path, 'r') as file:
            lines = file.readlines()

        nth_line = 3
        year_line = lines[nth_line - 1]

        # Split the input string by spaces
        elements = year_line.split()

        # Modify warmup year
        elements[0] = str(warmup)

        # Reconstruct the result string while maintaining spaces
        result_string = '{: <12} {: <11} {: <11} {: <10} {: <10} {: <10} \n'.format(*elements)

        lines[nth_line - 1] = result_string

        with open(time_sim_path, 'w') as file:
            file.writelines(lines)

    def _enable_disable_csv_print(
        self,
        enable: bool = True
    ) -> None:

        '''
        Enable or disable print in the `print.prt` file.
        '''

        # read
        nth_line = 7

        # time_sim_path = f"{self.root_folder}\\{'time.sim'}"
        print_prt_path = self.root_folder / 'print.prt'

        # Open the file in read mode and read its contents
        with open(print_prt_path, 'r') as file:
            lines = file.readlines()

        if enable:
            lines[nth_line - 1] = 'y' + lines[nth_line - 1][1:]
        else:
            lines[nth_line - 1] = 'n' + lines[nth_line - 1][1:]

        with open(print_prt_path, 'w') as file:
            file.writelines(lines)

    def enable_csv_print(
        self
    ) -> None:

        '''
        Enable print in the `print.prt` file.
        '''

        self._enable_disable_csv_print(enable=True)

    def disable_csv_print(
        self
    ) -> None:

        '''
        Disable print in the `print.prt` file.
        '''

        self._enable_disable_csv_print(enable=False)

    def register_file(
        self,
        filename: str,
        has_units: bool = False,
        usecols: typing.Optional[list[str]] = None,
        filter_by: typing.Optional[str] = None
    ) -> FileReader:

        '''
        Register a file to work with in the SWAT+ model.

        Parameters:
            filename (str): Path to the file to register, located in the `TxtInOut` folder.
            has_units (bool): If True, the second row of the file contains units.
            usecols (list[str]): List of column names to read from the file.
            filter_by (str): A pandas query string to filter rows from the file.

        Returns:
            A FileReader instance for the registered file.
        '''

        file_path = self.root_folder / filename

        return FileReader(file_path, has_units, usecols, filter_by)

    def _copy_swat(
        self,
        target_dir: str | pathlib.Path,
    ) -> pathlib.Path:

        '''
        Copy the required contents from the input folder associated with this
        `TxtinoutReader` instance to a target directory for SWAT+ simulation.
        '''

        dest_path = pathlib.Path(target_dir)

        # Copy files from source folder
        for file in self.root_folder.iterdir():
            if file.is_dir() or file.name.endswith(self.IGNORED_FILE_PATTERNS):
                continue
            shutil.copy2(file, dest_path / file.name)

        return dest_path

    def _run_swat(
        self,
    ) -> None:

        '''
        Run the SWAT+ simulation.
        '''

        # Run simulation
        try:
            process = subprocess.Popen(
                [str(self.swat_exe_path.resolve())],
                cwd=str(self.root_folder.resolve()),  # Sets working dir just for this subprocess
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,  # Line buffered
                text=True   # Handles text output
            )

            # Real-time output handling
            if process.stdout:
                for line in process.stdout:
                    clean_line = line.strip()
                    if clean_line:
                        logger.info(clean_line)

            # Wait for process and check for errors
            return_code = process.wait()
            if return_code != 0:
                stderr = process.stderr.read() if process.stderr else None
                raise subprocess.CalledProcessError(
                    return_code,
                    process.args,
                    stderr=stderr
                )

        except Exception as e:
            logger.error(f"Failed to run SWAT: {str(e)}")
            raise

    def run_swat(
        self,
        params: typing.Optional[ParamsType] = None,
    ) -> pathlib.Path:

        '''
        Run the SWAT+ simulation with optional parameter changes.

        Args:
            params (ParamsType, optional): Nested dictionary specifying parameter changes to apply.

                The `params` dictionary should follow this structure:

                ```python
                params = {
                    "<input_file>": {
                        "has_units": bool,              # Optional. Whether the file has units information (default is False)
                        "<parameter_name>": [           # One or more changes to apply to the parameter
                            {
                                "value": float,         # New value to assign
                                "change_type": str,     # (Optional) One of: 'absval' (default), 'abschg', 'pctchg'
                                "filter_by": str        # (Optional) pandas `.query()` filter string to select rows
                            },
                            # ... more changes
                        ]
                    },
                    # ... more input files
                }
                ```

        Returns:
            Path where the SWAT+ simulation was executed.

        Example:
            ```python
            params = {
                'plants.plt': {
                    'has_units': False,
                    'bm_e': [
                        {'value': 100, 'change_type': 'absval', 'filter_by': 'name == "agrl"'},
                        {'value': 110, 'change_type': 'absval', 'filter_by': 'name == "almd"'},
                    ],
                },
            }

            reader.run_swat(params)
            ```
        '''

        _params = params or {}

        _validate_params(_params)

        # Modify files for simulation
        for filename, file_params in _params.items():
            has_units = file_params.get('has_units', False)

            # adding block only for mypy validation, as it's already validated in _validate_params
            if not isinstance(has_units, bool):
                raise TypeError(f"`has_units` for file '{filename}' must be a boolean.")

            file = self.register_file(
                filename,
                has_units=has_units
            )
            df = file.df

            for param_name, param_spec in file_params.items():
                if param_name in self.RESERVED_PARAMS:
                    continue  # Skip reserved parameters

                # adding block only for mypy validation, as it's already validated in _validate_params
                if isinstance(param_spec, bool):
                    raise TypeError(f"Unexpected bool value for parameter '{param_name}' in file '{filename}'")

                # Normalize to list of changes
                changes = param_spec if isinstance(param_spec, list) else [param_spec]

                # Process each parameter change
                for change in changes:
                    _apply_param_change(df, param_name, change)

            # Store the modified file
            file.overwrite_file()

        # run simulation
        self._run_swat()

        return self.root_folder

    def run_swat_in_other_dir(
        self,
        target_dir: str | pathlib.Path,
        params: typing.Optional[ParamsType] = None,
    ) -> pathlib.Path:

        '''
        Run the SWAT+ model in a specified directory, with optional parameter modifications.
        This method copies the necessary input files from the current project into the
        given `target_dir`, applies any parameter changes specified in `params`, and
        executes the SWAT+ simulation there.

        Args:
            target_dir (str or Path): Path to the directory where the simulation will be done.

            params (ParamsType, optional): Nested dictionary specifying parameter changes.

                The `params` dictionary should follow this structure:

                ```python
                params = {
                    "<input_file>": {
                        "has_units": bool,              # Optional. Whether the file has units information (default is False)
                        "<parameter_name>": [           # One or more changes to apply to the parameter
                            {
                                "value": float,         # New value to assign
                                "change_type": str,     # (Optional) One of: 'absval' (default), 'abschg', 'pctchg'
                                "filter_by": str        # (Optional) pandas `.query()` filter string to select rows
                            },
                            # ... more changes
                        ]
                    },
                    # ... more input files
                }
                ```

        Returns:
            The path to the directory where the SWAT+ simulation was executed.

        Example:
            ```python
            params = {
                'plants.plt': {
                    'has_units': False,
                    'bm_e': [
                        {'value': 100, 'change_type': 'absval', 'filter_by': 'name == "agrl"'},
                        {'value': 110, 'change_type': 'absval', 'filter_by': 'name == "almd"'},
                    ],
                },
            }

            with tempfile.TemporaryDirectory() as tmp_dir:
                simulation = pySWATPlus.TxtinoutReader.run_swat_in_other_dir(
                    target_dir=tmp_dir,
                    params=params
                )
            ```
        '''

        # Validate target_dir
        if not isinstance(target_dir, (str, pathlib.Path)):
            raise TypeError("target_dir must be a string or Path object")

        target_dir = pathlib.Path(target_dir).resolve()

        # Create the directory if it does not exist
        target_dir.mkdir(parents=True, exist_ok=True)

        tmp_path = self._copy_swat(target_dir=target_dir)
        reader = TxtinoutReader(tmp_path)

        return reader.run_swat(params)

    def _run_swat_in_other_dir_unified(
        self,
        target_dir: str | pathlib.Path,
        params: typing.Optional[ParamsType] = None,
        begin_and_end_year: typing.Optional[tuple[int, int]] = None,
        warmup: typing.Optional[int] = None,
        disable_print_prt: typing.Optional[dict[str, dict[str, bool]]] = None
    ) -> pathlib.Path:

        '''
        Run the SWAT+ model in a specified directory, with optional parameter modifications.
        This method copies the necessary input files from the current project into the
        given `target_dir`, applies any parameter changes, and executes the SWAT+ simulation there.

        Args:
            target_dir (str or Path): Path to the directory where the simulation will be done.

            params (ParamsType): Nested dictionary specifying parameter changes.

                The `params` dictionary should follow this structure:

                ```python
                params = {
                    "<input_file>": {
                        "has_units": bool,              # Optional. Whether the file has units information (default is False)
                        "<parameter_name>": [           # One or more changes to apply to the parameter
                            {
                                "value": float,         # New value to assign
                                "change_type": str,     # (Optional) One of: 'absval' (default), 'abschg', 'pctchg'
                                "filter_by": str        # (Optional) pandas `.query()` filter string to select rows
                            },
                            # ... more changes
                        ]
                    },
                    # ... more input files
                }
                ```

            begin_and_end_year (tuple[int, int]): A tuple of begin and end years of the simulation in YYYY format.

            warmup (int): A positive integer representing the number of warm-up years (e.g., 1).

            disable_print_prt (dict[str, dict[str, bool]]):
                A dictionary where each outer key represents an object from the `print.prt` file,
                    and the corresponding value is a dictionary with inner keys:
                    `daily`, `monthly`, `yearly`, or `avann`. All inner options default to `True`
                    unless explicitly set to `False`. An error will be raised if an outer key
                    is provided with an empty dictionary.

        Returns:
            The path to the directory where the SWAT+ simulation was executed.

        Example:
            ```python
            simulation = pySWATPlus.TxtinoutReader.run_swat_in_other_dir_new_method(
                target_dir="C:\\\\Users\\\\Username\\\\simulation_folder",
                params={
                    'plants.plt': {
                        'has_units': False,
                        'bm_e': [
                            {'value': 100, 'change_type': 'absval', 'filter_by': 'name == "agrl"'},
                            {'value': 110, 'change_type': 'absval', 'filter_by': 'name == "almd"'},
                        ],
                    },
                },
                begin_and_end_year=(2012, 2016),
                warmup=1,
                disable_print_prt = {
                    'channel_sd': {'daily': False},
                    'channel_sdmorph': {'monthly': False}
                }
            )
            ```
        '''

        # Validate target directory
        if not isinstance(target_dir, (str, pathlib.Path)):
            raise TypeError('target_dir must be a string or Path object')

        target_dir = pathlib.Path(target_dir).resolve()

        # Create the directory if it does not exist and copy necessary files
        target_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self._copy_swat(target_dir=target_dir)

        # Initialize new TxtinoutReader class
        reader = TxtinoutReader(tmp_path)

        # Set simulation range time
        if begin_and_end_year is not None:
            if not isinstance(begin_and_end_year, tuple):
                raise TypeError('begin_end_years must be a tuple')
            if len(begin_and_end_year) != 2:
                raise ValueError('begin_end_years must contain exactly two elements')
            begin, end = begin_and_end_year
            reader.set_begin_and_end_year(
                begin=begin,
                end=end
            )

        # Set warmup period
        if warmup is not None:
            reader.set_warmup_year(
                warmup=warmup
            )

        # update print.prt file to write output
        if disable_print_prt is not None:
            if not isinstance(disable_print_prt, dict):
                raise TypeError('disable_print_prt must be a dictionary')
            if len(disable_print_prt) == 0:
                raise ValueError('disable_print_prt cannot be an empty dictionary')
            default_dict = {
                'daily': True,
                'monthly': True,
                'yearly': True,
                'avann': True
            }
            for key, val in disable_print_prt.items():
                if not isinstance(val, dict):
                    raise ValueError(f'Value of key "{key}" must be a dictionary')
                if len(val) == 0:
                    raise ValueError(f'Value of key "{key}" cannot be an empty dictionary')
                key_dict = default_dict.copy()
                for sub_key, sub_val in val.items():
                    if sub_key not in key_dict:
                        raise ValueError(f'Sub-key "{sub_key}" for key "{key}" is not valid')
                    key_dict[sub_key] = sub_val
                reader.enable_object_in_print_prt(
                    obj=key,
                    daily=key_dict['daily'],
                    monthly=key_dict['monthly'],
                    yearly=key_dict['yearly'],
                    avann=key_dict['avann']
                )

        # run the SWAT+ simulation
        output = reader.run_swat(params=params)

        return output
