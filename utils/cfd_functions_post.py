import os
import pandas as pd
import numpy as np
from bluemath_tk.waves.spectra import spectral_analysis 

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

def get_waveparams_from_gauge(df_gauges, reflevel=0.0):
    """
    Extract wave parameters from gauge data.
    """
    df_gauges = df_gauges - reflevel
    
    df_out = pd.DataFrame(index=df_gauges.columns)

    #Statistical Analysis [Hrms]
    sigma = df_gauges.std(axis=0, ddof=0) 
    df_out['Hrms'] = 2 * np.sqrt(2) * sigma

    #Spectran Analysis [Hs, Hss, Hig, Hvlf ]
    time_values = df_gauges.index.values
    delttbl = np.median(np.diff(time_values))
    
    Hs_list, Hss_list, Hig_list, Hvlf_list = [], [], [], []
    for gauge_name in df_gauges.columns:
        series = df_gauges[gauge_name].values
        Hs, Hss, Hig, Hvlf = spectral_analysis(series, delttbl)
        Hs_list.append(Hs)
        Hss_list.append(Hss)
        Hig_list.append(Hig)
        Hvlf_list.append(Hvlf)

    df_out["Hs"] = Hs_list
    df_out["Hss"] = Hss_list
    df_out["Hig"] = Hig_list
    df_out["Hvlf"] = Hvlf_list

    #Set-up
    df_out['Setup'] = np.mean(df_gauges.values, axis=0)

    return df_out

