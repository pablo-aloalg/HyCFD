import os
import pandas as pd

def readWaveGauge(case_dir, func_name, alphaIso=0.5):
   
    post_output_dir = os.path.join(case_dir, 'postProcessing', func_name, '0')
    
    if not os.path.exists(post_output_dir):
        raise FileNotFoundError(f"Post-processing output directory '{post_output_dir}' not found.")

    if func_name == 'surfaceElevationAnyName':
        output_df = read_surfaceelevation_dat(post_output_dir)

    return output_df

def read_surfaceelevation_dat(post_output_dir):
    
    if not os.path.exists(os.path.join(post_output_dir, 'surfaceElevation.dat')):
        raise FileNotFoundError(f"Post-processing file surfaceElevation.dat not found in '{post_output_dir}'.")

    data = pd.read_csv(os.path.join(post_output_dir, 'surfaceElevation.dat'), sep='\t', header=0)
    
    if data.shape[0] < 2 or data.shape[1] < 2:
        raise ValueError("Invalid surface elevation data format.")

    if not data.iloc[3:, 0].is_monotonic_increasing:
        raise ValueError("Time values in surface elevation data are not monotonically increasing.")

    data = data.iloc[3:].reset_index(drop=True)
    data = data.set_index('Time')
    return data

def get_waveparams_from_gauge(df_gauges):
    """
    Extract wave parameters from gauge data.
    """
