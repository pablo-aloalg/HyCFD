import os
import re

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

def read_foam_points(file):
    with open(file, 'r') as f:
        n = None
    
        for line in f:
            t = line.strip()
            if not t or t.startswith('//') or t.startswith('/*'):
                continue
            if re.match(r'^\d+$', t):
                n = int(t)
                break
        if n is None:
            raise ValueError(f"Failed to find point count in {file}")
        
        # Skip until opening parenthesis '('
        for line in f:
            if line.strip() == '(':
                break
        
        points = []
        for _ in range(n):
            line = f.readline().strip()
            match = re.match(r'\(\s*([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s*\)', line)
            if match:
                points.append([float(match.group(1)), float(match.group(2)), float(match.group(3))])
            else:
                raise ValueError(f"Invalid point format: {line}")
    
    return np.array(points)

def read_foam_faces_quad(file):
    with open(file, 'r') as f:
        n = None

        # Find the number of faces
        for line in f:
            t = line.strip()
            if not t or t.startswith('//') or t.startswith('/*'):
                continue
            if re.match(r'^\d+$', t):
                n = int(t)
                break
        if n is None:
            raise ValueError(f"Failed to find face count in {file}")

        # Skip until opening parenthesis '('
        for line in f:
            if line.strip() == '(':
                break

        # Read faces
        F = np.zeros((n, 4), dtype=int)
        for i in range(n):
            line = f.readline().strip()
            # Number of points in this face
            match_np = re.match(r'^(\d+)\s*\(', line)
            if not match_np:
                raise ValueError(f"Invalid face line format: {line}")
            np_count = int(match_np.group(1))
            if np_count != 4:
                raise ValueError(f"This reader assumes quad faces. Face {i+1} has {np_count} points.")

            # Extract the numbers inside parentheses
            nums = re.findall(r'\d+', line)
            F[i, :] = [int(x) for x in nums[1:]]  # skip the first number (np_count)

    return F

def read_foam_label_list(file):
    with open(file, 'r') as f:
        n = None

        # Find the number of entries
        for line in f:
            t = line.strip()
            if not t or t.startswith('//') or t.startswith('/*'):
                continue
            if re.match(r'^\d+$', t):
                n = int(t)
                break

        if n is None:
            raise ValueError(f"Failed to find list count in {file}")

        # Skip until opening parenthesis '('
        for line in f:
            if line.strip() == '(':
                break

        # Read n integers
        values = []
        while len(values) < n:
            line = f.readline()
            if not line:
                break
            nums = re.findall(r'-?\d+', line)
            values.extend(int(x) for x in nums)

        if len(values) != n:
            raise ValueError(f"Expected {n} entries, got {len(values)}")

    return np.array(values, dtype=int)

def read_foam_internal_scalar(file, nCells):
    with open(file, 'r') as f:
        txt = f.read()

    # ---- uniform case ----
    m = re.search(r'internalField\s+uniform\s+([-\deE\.+]+)\s*;', txt)
    if m:
        val = float(m.group(1))
        return np.full(nCells, val)

    # ---- nonuniform List<scalar> case ----
    m = re.search(
        r'internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(\s*([^)]*?)\)\s*;',
        txt,
        re.DOTALL
    )

    if not m:
        raise ValueError(f"Cannot parse internalField in {file}")

    n = int(m.group(1))
    nums = np.fromstring(m.group(2), sep=' ')

    if len(nums) != n:
        raise ValueError(
            f"Parsed {len(nums)} scalars but expected {n} in {file}"
        )

    if nCells != n:
        print(
            f"Warning: nCells={nCells} but internalField has {n} values. "
            f"Using internalField length."
        )

    return nums.reshape(-1)