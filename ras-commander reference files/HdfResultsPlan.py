"""
HdfResultsPlan: A module for extracting and analyzing HEC-RAS plan HDF file results.

Attribution:
    Substantial code sourced/derived from https://github.com/fema-ffrd/rashdf
    Copyright (c) 2024 fema-ffrd, MIT license

Description:
    Provides static methods for extracting unsteady flow results, volume accounting,
    and reference data from HEC-RAS plan HDF files.

Available Functions:
    - get_unsteady_info: Extract unsteady attributes
    - get_unsteady_summary: Extract unsteady summary data
    - get_volume_accounting: Extract volume accounting data
    - get_runtime_data: Extract runtime and compute time data

Note:
    All methods are static and designed to be used without class instantiation.
"""

from typing import Dict, List, Union, Optional
from pathlib import Path
import h5py
import pandas as pd
import xarray as xr
from .Decorators import standardize_input, log_call
from .HdfUtils import HdfUtils
from .HdfResultsXsec import HdfResultsXsec
from .LoggingConfig import get_logger
import numpy as np
from datetime import datetime
from .RasPrj import ras

logger = get_logger(__name__)


class HdfResultsPlan:
    """
    Handles extraction of results data from HEC-RAS plan HDF files.

    This class provides static methods for accessing and analyzing:
        - Unsteady flow results
        - Volume accounting data
        - Runtime statistics
        - Reference line/point time series outputs

    All methods use:
        - @standardize_input decorator for consistent file path handling
        - @log_call decorator for operation logging
        - HdfUtils class for common HDF operations

    Note:
        No instantiation required - all methods are static.
    """

    @staticmethod
    @log_call
    @standardize_input(file_type='plan_hdf')
    def get_unsteady_info(hdf_path: Path) -> pd.DataFrame:
        """
        Get unsteady attributes from a HEC-RAS HDF plan file.

        Args:
            hdf_path (Path): Path to the HEC-RAS plan HDF file.
            ras_object (RasPrj, optional): Specific RAS object to use. If None, uses the global ras instance.

        Returns:
            pd.DataFrame: A DataFrame containing the decoded unsteady attributes.

        Raises:
            FileNotFoundError: If the specified HDF file is not found.
            KeyError: If the "Results/Unsteady" group is not found in the HDF file.
        """
        try:
            with h5py.File(hdf_path, 'r') as hdf_file:
                if "Results/Unsteady" not in hdf_file:
                    raise KeyError("Results/Unsteady group not found in the HDF file.")
                
                # Create dictionary from attributes and decode byte strings
                attrs_dict = {}
                for key, value in dict(hdf_file["Results/Unsteady"].attrs).items():
                    if isinstance(value, bytes):
                        attrs_dict[key] = value.decode('utf-8')
                    else:
                        attrs_dict[key] = value
                
                # Create DataFrame with a single row index
                return pd.DataFrame(attrs_dict, index=[0])
                
        except FileNotFoundError:
            raise FileNotFoundError(f"HDF file not found: {hdf_path}")
        except Exception as e:
            raise RuntimeError(f"Error reading unsteady attributes: {str(e)}")
        
    @staticmethod
    @log_call
    @standardize_input(file_type='plan_hdf')
    def get_unsteady_summary(hdf_path: Path) -> pd.DataFrame:
        """
        Get results unsteady summary attributes from a HEC-RAS HDF plan file.

        Args:
            hdf_path (Path): Path to the HEC-RAS plan HDF file.
            ras_object (RasPrj, optional): Specific RAS object to use. If None, uses the global ras instance.

        Returns:
            pd.DataFrame: A DataFrame containing the decoded results unsteady summary attributes.

        Raises:
            FileNotFoundError: If the specified HDF file is not found.
            KeyError: If the "Results/Unsteady/Summary" group is not found in the HDF file.
        """
        try:           
            with h5py.File(hdf_path, 'r') as hdf_file:
                if "Results/Unsteady/Summary" not in hdf_file:
                    raise KeyError("Results/Unsteady/Summary group not found in the HDF file.")
                
                # Create dictionary from attributes and decode byte strings
                attrs_dict = {}
                for key, value in dict(hdf_file["Results/Unsteady/Summary"].attrs).items():
                    if isinstance(value, bytes):
                        attrs_dict[key] = value.decode('utf-8')
                    else:
                        attrs_dict[key] = value
                
                # Create DataFrame with a single row index
                return pd.DataFrame(attrs_dict, index=[0])
                
        except FileNotFoundError:
            raise FileNotFoundError(f"HDF file not found: {hdf_path}")
        except Exception as e:
            raise RuntimeError(f"Error reading unsteady summary attributes: {str(e)}")
        
    @staticmethod
    @log_call
    @standardize_input(file_type='plan_hdf')
    def get_volume_accounting(hdf_path: Path) -> Optional[pd.DataFrame]:
        """
        Get volume accounting attributes from a HEC-RAS HDF plan file.

        Args:
            hdf_path (Path): Path to the HEC-RAS plan HDF file.
            ras_object (RasPrj, optional): Specific RAS object to use. If None, uses the global ras instance.

        Returns:
            Optional[pd.DataFrame]: DataFrame containing the decoded volume accounting attributes,
                                  or None if the group is not found.

        Raises:
            FileNotFoundError: If the specified HDF file is not found.
        """
        try:
            with h5py.File(hdf_path, 'r') as hdf_file:
                if "Results/Unsteady/Summary/Volume Accounting" not in hdf_file:
                    return None
                
                # Get attributes and decode byte strings
                attrs_dict = {}
                for key, value in dict(hdf_file["Results/Unsteady/Summary/Volume Accounting"].attrs).items():
                    if isinstance(value, bytes):
                        attrs_dict[key] = value.decode('utf-8')
                    else:
                        attrs_dict[key] = value
                
                return pd.DataFrame(attrs_dict, index=[0])
                
        except FileNotFoundError:
            raise FileNotFoundError(f"HDF file not found: {hdf_path}")
        except Exception as e:
            raise RuntimeError(f"Error reading volume accounting attributes: {str(e)}")

    @staticmethod
    @standardize_input(file_type='plan_hdf')
    def get_runtime_data(hdf_path: Path) -> Optional[pd.DataFrame]:
        """
        Extract detailed runtime and computational performance metrics from HDF file.

        Args:
            hdf_path (Path): Path to HEC-RAS plan HDF file
            ras_object (RasPrj, optional): Specific RAS object to use. If None, uses the global ras instance.

        Returns:
            Optional[pd.DataFrame]: DataFrame containing runtime statistics or None if data cannot be extracted

        Notes:
            - Times are reported in multiple units (ms, s, hours)
            - Compute speeds are calculated as simulation-time/compute-time ratios
            - Process times include: geometry, preprocessing, event conditions, 
              and unsteady flow computations
        """
        try:
            if hdf_path is None:
                logger.error(f"Could not find HDF file for input")
                return None

            with h5py.File(hdf_path, 'r') as hdf_file:
                logger.info(f"Extracting Plan Information from: {Path(hdf_file.filename).name}")
                plan_info = hdf_file.get('/Plan Data/Plan Information')
                if plan_info is None:
                    logger.warning("Group '/Plan Data/Plan Information' not found.")
                    return None

                # Extract plan information
                plan_name = HdfUtils.convert_ras_string(plan_info.attrs.get('Plan Name', 'Unknown'))
                start_time_str = HdfUtils.convert_ras_string(plan_info.attrs.get('Simulation Start Time', 'Unknown'))
                end_time_str = HdfUtils.convert_ras_string(plan_info.attrs.get('Simulation End Time', 'Unknown'))

                try:
                    # Check if times are already datetime objects
                    if isinstance(start_time_str, datetime):
                        start_time = start_time_str
                    else:
                        start_time = datetime.strptime(start_time_str, "%d%b%Y %H:%M:%S")
                        
                    if isinstance(end_time_str, datetime):
                        end_time = end_time_str
                    else:
                        end_time = datetime.strptime(end_time_str, "%d%b%Y %H:%M:%S")
                        
                    simulation_duration = end_time - start_time
                    simulation_hours = simulation_duration.total_seconds() / 3600
                except ValueError as e:
                    logger.error(f"Error parsing simulation times: {e}")
                    return None

                logger.info(f"Plan Name: {plan_name}")
                logger.info(f"Simulation Duration (hours): {simulation_hours}")

                # Extract compute processes data
                compute_processes = hdf_file.get('/Results/Summary/Compute Processes')
                if compute_processes is None:
                    logger.warning("Dataset '/Results/Summary/Compute Processes' not found.")
                    return None

                # Process compute times
                process_names = [HdfUtils.convert_ras_string(name) for name in compute_processes['Process'][:]]
                filenames = [HdfUtils.convert_ras_string(filename) for filename in compute_processes['Filename'][:]]
                completion_times = compute_processes['Compute Time (ms)'][:]

                compute_processes_df = pd.DataFrame({
                    'Process': process_names,
                    'Filename': filenames,
                    'Compute Time (ms)': completion_times,
                    'Compute Time (s)': completion_times / 1000,
                    'Compute Time (hours)': completion_times / (1000 * 3600)
                })

                # Create summary DataFrame
                compute_processes_summary = {
                    'Plan Name': [plan_name],
                    'File Name': [Path(hdf_file.filename).name],
                    'Simulation Start Time': [start_time_str],
                    'Simulation End Time': [end_time_str],
                    'Simulation Duration (s)': [simulation_duration.total_seconds()],
                    'Simulation Time (hr)': [simulation_hours]
                }

                # Add process-specific times
                process_types = {
                    'Completing Geometry': 'Completing Geometry (hr)',
                    'Preprocessing Geometry': 'Preprocessing Geometry (hr)',
                    'Completing Event Conditions': 'Completing Event Conditions (hr)',
                    'Unsteady Flow Computations': 'Unsteady Flow Computations (hr)'
                }

                for process, column in process_types.items():
                    time_value = compute_processes_df[
                        compute_processes_df['Process'] == process
                    ]['Compute Time (hours)'].values[0] if process in process_names else 'N/A'
                    compute_processes_summary[column] = [time_value]

                # Add total process time
                total_time = compute_processes_df['Compute Time (hours)'].sum()
                compute_processes_summary['Complete Process (hr)'] = [total_time]

                # Calculate speeds
                if compute_processes_summary['Unsteady Flow Computations (hr)'][0] != 'N/A':
                    compute_processes_summary['Unsteady Flow Speed (hr/hr)'] = [
                        simulation_hours / compute_processes_summary['Unsteady Flow Computations (hr)'][0]
                    ]
                else:
                    compute_processes_summary['Unsteady Flow Speed (hr/hr)'] = ['N/A']

                compute_processes_summary['Complete Process Speed (hr/hr)'] = [
                    simulation_hours / total_time
                ]

                return pd.DataFrame(compute_processes_summary)

        except Exception as e:
            logger.error(f"Error in get_runtime_data: {str(e)}")
            return None

    @staticmethod
    @log_call
    @standardize_input(file_type='plan_hdf')
    def get_reference_timeseries(hdf_path: Path, reftype: str) -> pd.DataFrame:
        """
        Get reference line or point timeseries output from HDF file.

        Args:
            hdf_path (Path): Path to HEC-RAS plan HDF file
            reftype (str): Type of reference data ('lines' or 'points')
            ras_object (RasPrj, optional): Specific RAS object to use. If None, uses the global ras instance.

        Returns:
            pd.DataFrame: DataFrame containing reference timeseries data
        """
        try:
            with h5py.File(hdf_path, 'r') as hdf_file:
                base_path = "Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series"
                ref_path = f"{base_path}/Reference {reftype.capitalize()}"
                
                if ref_path not in hdf_file:
                    logger.warning(f"Reference {reftype} data not found in HDF file")
                    return pd.DataFrame()

                ref_group = hdf_file[ref_path]
                time_data = hdf_file[f"{base_path}/Time"][:]
                
                dfs = []
                for ref_name in ref_group.keys():
                    ref_data = ref_group[ref_name][:]
                    df = pd.DataFrame(ref_data, columns=[ref_name])
                    df['Time'] = time_data
                    dfs.append(df)

                if not dfs:
                    return pd.DataFrame()

                return pd.concat(dfs, axis=1)

        except Exception as e:
            logger.error(f"Error reading reference {reftype} timeseries: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    @log_call
    @standardize_input(file_type='plan_hdf')
    def get_reference_summary(hdf_path: Path, reftype: str) -> pd.DataFrame:
        """
        Get reference line or point summary output from HDF file.

        Args:
            hdf_path (Path): Path to HEC-RAS plan HDF file
            reftype (str): Type of reference data ('lines' or 'points')
            ras_object (RasPrj, optional): Specific RAS object to use. If None, uses the global ras instance.

        Returns:
            pd.DataFrame: DataFrame containing reference summary data
        """
        try:
            with h5py.File(hdf_path, 'r') as hdf_file:
                base_path = "Results/Unsteady/Output/Output Blocks/Base Output/Summary Output"
                ref_path = f"{base_path}/Reference {reftype.capitalize()}"
                
                if ref_path not in hdf_file:
                    logger.warning(f"Reference {reftype} summary data not found in HDF file")
                    return pd.DataFrame()

                ref_group = hdf_file[ref_path]
                dfs = []
                
                for ref_name in ref_group.keys():
                    ref_data = ref_group[ref_name][:]
                    if ref_data.ndim == 2:
                        df = pd.DataFrame(ref_data.T, columns=['Value', 'Time'])
                    else:
                        df = pd.DataFrame({'Value': ref_data})
                    df['Reference'] = ref_name
                    dfs.append(df)

                if not dfs:
                    return pd.DataFrame()

                return pd.concat(dfs, ignore_index=True)

        except Exception as e:
            logger.error(f"Error reading reference {reftype} summary: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    @log_call
    @standardize_input(file_type='plan_hdf')
    def get_compute_messages(hdf_path: Path) -> str:
        """
        Extract compute messages from a HEC-RAS plan HDF file.
        
        This method retrieves the computation log messages stored in the HDF file,
        which include timing information, computation tasks, and performance metrics.
        If the output exceeds 10,000 tokens, it will be truncated with the last 50 lines
        preserved.

        Args:
            hdf_path (Path): Path to the HEC-RAS plan HDF file.

        Returns:
            str: Formatted compute messages string. Returns an error message if
                 compute messages are not found or cannot be read.

        Raises:
            FileNotFoundError: If the specified HDF file is not found.
            RuntimeError: If there's an error reading the compute messages.
        """
        try:
            with h5py.File(hdf_path, 'r') as hdf_file:
                compute_messages_path = '/Results/Summary/Compute Messages (text)'
                
                if compute_messages_path not in hdf_file:
                    return "Compute messages not found. The simulation may not have completed or results were not saved properly."
                
                # Extract the compute messages
                compute_messages_dataset = hdf_file[compute_messages_path]
                
                # Handle different data types
                if isinstance(compute_messages_dataset, h5py.Dataset):
                    data = compute_messages_dataset[()]
                    
                    # Convert to string based on data type
                    if isinstance(data, bytes):
                        messages_text = data.decode('utf-8')
                    elif isinstance(data, np.ndarray):
                        if data.dtype.kind == 'S':  # String array
                            # Join array of strings
                            messages_text = '\n'.join([item.decode('utf-8') if isinstance(item, bytes) else str(item) 
                                                      for item in data])
                        else:
                            messages_text = str(data)
                    else:
                        messages_text = str(data)
                else:
                    return f"Unexpected data type for compute messages: {type(compute_messages_dataset)}"
                
                # Format the output
                formatted_output = HdfResultsPlan._format_compute_messages(messages_text, str(hdf_path))
                
                # Check token count and truncate if necessary
                # Rough approximation: 1 token ≈ 4 characters
                max_chars = 10000 * 4  # 40,000 characters for 10k tokens
                
                if len(formatted_output) > max_chars:
                    # Truncate but preserve last 50 lines
                    lines = formatted_output.split('\n')
                    last_50_lines = lines[-50:] if len(lines) > 50 else lines
                    
                    # Find how many characters we can include from the beginning
                    last_50_text = '\n'.join(last_50_lines)
                    truncation_notice = "\n\n[OUTPUT TRUNCATED: Response exceeded 10,000 tokens. Showing beginning and last 50 lines.]\n\n"
                    
                    available_chars = max_chars - len(last_50_text) - len(truncation_notice)
                    truncated_beginning = formatted_output[:available_chars]
                    
                    # Find last complete line in truncated beginning
                    last_newline = truncated_beginning.rfind('\n')
                    if last_newline > 0:
                        truncated_beginning = truncated_beginning[:last_newline]
                    
                    formatted_output = truncated_beginning + truncation_notice + last_50_text
                
                return formatted_output
                
        except FileNotFoundError:
            raise FileNotFoundError(f"HDF file not found: {hdf_path}")
        except Exception as e:
            logger.error(f"Error reading compute messages: {str(e)}")
            raise RuntimeError(f"Error reading compute messages: {str(e)}")

    @staticmethod
    def _format_compute_messages(messages_text: str, hdf_file_path: str) -> str:
        """
        Format compute messages for better readability.
        
        Args:
            messages_text (str): Raw compute messages text
            hdf_file_path (str): Path to the HDF file for reference
            
        Returns:
            str: Formatted compute messages
        """
        lines = messages_text.split('\r\n') if '\r\n' in messages_text else messages_text.split('\n')
        
        formatted_parts = [
            f"Compute Messages from: {Path(hdf_file_path).name}",
            "=" * 80,
            ""
        ]
        
        # Track sections for organized output
        current_section = None
        computation_tasks = []
        computation_speeds = []
        general_messages = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Categorize messages
            if 'Computation Task' in line and '\t' in line:
                computation_tasks.append(line)
            elif 'Computation Speed' in line and '\t' in line:
                computation_speeds.append(line)
            else:
                general_messages.append(line)
        
        # Add general messages first
        if general_messages:
            formatted_parts.append("General Messages:")
            formatted_parts.append("-" * 40)
            for msg in general_messages:
                if ':' in msg and not msg.startswith('http'):
                    key, value = msg.split(':', 1)
                    formatted_parts.append(f"{key.strip():40} : {value.strip()}")
                else:
                    formatted_parts.append(msg)
            formatted_parts.append("")
        
        # Add computation tasks
        if computation_tasks:
            formatted_parts.append("Computation Tasks:")
            formatted_parts.append("-" * 60)
            formatted_parts.append(f"{'Task':<40} {'Time':<20}")
            formatted_parts.append("-" * 60)
            for task_line in computation_tasks:
                parts = task_line.split('\t')
                if len(parts) >= 2:
                    task = parts[0].replace('Computation Task', '').strip()
                    time = parts[1].strip()
                    formatted_parts.append(f"{task:<40} {time:<20}")
            formatted_parts.append("")
        
        # Add computation speeds
        if computation_speeds:
            formatted_parts.append("Computation Speed:")
            formatted_parts.append("-" * 60)
            formatted_parts.append(f"{'Task':<40} {'Simulation/Runtime':<20}")
            formatted_parts.append("-" * 60)
            for speed_line in computation_speeds:
                parts = speed_line.split('\t')
                if len(parts) >= 2:
                    task = parts[0].replace('Computation Speed', '').strip()
                    speed = parts[1].strip()
                    formatted_parts.append(f"{task:<40} {speed:<20}")
            formatted_parts.append("")
        
        return '\n'.join(formatted_parts)