import os
import re

import pandas as pd
import numpy as np
import xarray as xr

from bluemath_tk.waves.spectra import spectral_analysis 

import sys
sys.path.append(os.path.dirname(__file__))
from utils.cfd_functions_formatter import read_foam_faces_quad, read_foam_points, read_foam_label_list, read_foam_internal_scalar, list_time_dirs, read_surfaceelevation_dat

def readWaveGauge(case_dir, func_name, alphaIso=0.5):
   
    post_output_dir = os.path.join(case_dir, 'postProcessing', func_name)
    
    if not os.path.exists(post_output_dir):
        raise FileNotFoundError(f"Post-processing output directory '{post_output_dir}' not found.")

    if func_name == 'surfaceElevationAnyName':

        time_dirs = list_time_dirs(post_output_dir)

        output_df_list = []
        for t_dir in time_dirs:
            t_dir_path = os.path.join(post_output_dir, t_dir)
            if os.path.isdir(t_dir_path):
                df = read_surfaceelevation_dat(t_dir_path)
                df.index = df.index.round(2)
                output_df_list.append(df)

        final_df = output_df_list[0].copy()

        for df in output_df_list[1:]:
            restart_time = df.index.min()
            final_df = final_df[final_df.index < restart_time]
            final_df = pd.concat([final_df, df])

        final_df = final_df.sort_index()

    return final_df

def get_waveparams_from_gauge(df_gauges, reflevel=0.0, warmup_time=0.0):
    """
    Extract wave parameters from gauge data.
    """
    df_gauges = df_gauges - reflevel
    
    # Remove warmup time data
    df_gauges = df_gauges[df_gauges.index >= warmup_time]
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

def get_patch_faces_and_owner_cells(mesh_dir, patch_name):
    """
    Get face IDs and corresponding owner cells for a given patch in an OpenFOAM mesh.
    
    Parameters:
        mesh_dir (str): Path to the OpenFOAM mesh directory.
        patch_name (str): Name of the patch.
    
    Returns:
        face_ids (np.ndarray): 0-based face IDs for the patch.
        owner_cells (np.ndarray): 0-based owner cell IDs for these faces.
    """
    bnd_file = os.path.join(mesh_dir, 'boundary')
    if not os.path.isfile(bnd_file):
        raise FileNotFoundError(f"Cannot find boundary file: {bnd_file}")
    
    with open(bnd_file, 'r') as f:
        txt = f.read()
    
    # Match the patch block
    blk_match = re.search(rf'{patch_name}\s*\{{([^}}]*)\}}', txt, re.DOTALL)
    if not blk_match:
        raise ValueError(f"Patch {patch_name} not found in boundary file")
    
    blk = blk_match.group(1)
    
    # Extract nFaces and startFace
    n_faces_match = re.search(r'nFaces\s+(\d+)\s*;', blk)
    start_face_match = re.search(r'startFace\s+(\d+)\s*;', blk)
    if not n_faces_match or not start_face_match:
        raise ValueError(f"Patch block missing nFaces or startFace for patch {patch_name}")
    
    n_faces = int(n_faces_match.group(1))
    start_face = int(start_face_match.group(1))
    
    face_ids = np.arange(start_face, start_face + n_faces, dtype=int)  # 0-based face IDs
    
    # Read owner list and get corresponding owner cells
    owner_file = os.path.join(mesh_dir, 'owner')
    owner_list = read_foam_label_list(owner_file)
    
    if np.any(face_ids >= len(owner_list)):
        raise IndexError("Face IDs exceed owner list length")
    
    owner_cells = owner_list[face_ids]
    
    return face_ids, owner_cells

def get_cell_centers(mesh_dir):
    """
    Compute cell centers for an OpenFOAM polyMesh.
    
    Parameters
    ----------
    mesh_dir : str
        Path to constant/polyMesh folder
    
    Returns
    -------
    xC, yC, zC : np.ndarray, shape (nCells,)
        Cell center coordinates
    nCells : int
        Total number of cells
    """
    
    P   = read_foam_points(os.path.join(mesh_dir, 'points'))      # nPoints x 3
    F   = read_foam_faces_quad(os.path.join(mesh_dir, 'faces'))   # nFaces x 4
    own = read_foam_label_list(os.path.join(mesh_dir, 'owner'))   # nFaces
    nei = read_foam_label_list(os.path.join(mesh_dir, 'neighbour'))  # nInternalFaces
    
    nCells    = int(np.max(own)) + 1
    nInternal = len(nei)
    
    x = P[:,0]; y = P[:,1]; z = P[:,2]
    
    # face vertex indices (0-based)
    p1 = F[:,0]; p2 = F[:,1]; p3 = F[:,2]; p4 = F[:,3]
    
    # face bounding box
    faceMinX = np.min(np.column_stack([x[p1], x[p2], x[p3], x[p4]]), axis=1)
    faceMaxX = np.max(np.column_stack([x[p1], x[p2], x[p3], x[p4]]), axis=1)
    faceMinY = np.min(np.column_stack([y[p1], y[p2], y[p3], y[p4]]), axis=1)
    faceMaxY = np.max(np.column_stack([y[p1], y[p2], y[p3], y[p4]]), axis=1)
    faceMinZ = np.min(np.column_stack([z[p1], z[p2], z[p3], z[p4]]), axis=1)
    faceMaxZ = np.max(np.column_stack([z[p1], z[p2], z[p3], z[p4]]), axis=1)
    
    # internal faces only
    faceMinX_int = faceMinX[:nInternal]
    faceMaxX_int = faceMaxX[:nInternal]
    faceMinY_int = faceMinY[:nInternal]
    faceMaxY_int = faceMaxY[:nInternal]
    faceMinZ_int = faceMinZ[:nInternal]
    faceMaxZ_int = faceMaxZ[:nInternal]
    
    # accumarray-like min/max per cell
    cellIdx_all = np.concatenate([own, nei])
    
    def accum_min(indices, values, n):
        out = np.full(n, np.inf)
        for i,v in zip(indices, values):
            out[i] = min(out[i], v)
        return out
    
    def accum_max(indices, values, n):
        out = np.full(n, -np.inf)
        for i,v in zip(indices, values):
            out[i] = max(out[i], v)
        return out
    
    minX = accum_min(cellIdx_all, np.concatenate([faceMinX, faceMinX_int]), nCells)
    maxX = accum_max(cellIdx_all, np.concatenate([faceMaxX, faceMaxX_int]), nCells)
    minY = accum_min(cellIdx_all, np.concatenate([faceMinY, faceMinY_int]), nCells)
    maxY = accum_max(cellIdx_all, np.concatenate([faceMaxY, faceMaxY_int]), nCells)
    minZ = accum_min(cellIdx_all, np.concatenate([faceMinZ, faceMinZ_int]), nCells)
    maxZ = accum_max(cellIdx_all, np.concatenate([faceMaxZ, faceMaxZ_int]), nCells)
    
    # cell centers
    xC = 0.5*(minX + maxX)
    yC = 0.5*(minY + maxY)
    zC = 0.5*(minZ + maxZ)
    
    return xC, yC, zC, nCells

def select_patch_cells(mesh_dir, patch_name, zC, yC, y_min_phys=None, tol_z=1e-6):

    # --- Middle z-plane (optional thin slice) ---
    z_mid = np.median(zC)
    keep2D = np.abs(zC - z_mid) < tol_z

    # --- Get patch faces and owner cells ---
    patch_face_ids, patch_owner_cells = get_patch_faces_and_owner_cells(mesh_dir, patch_name)

    # Unique patch cells
    patch_cells = np.unique(patch_owner_cells)  # already 0-based in Python

    # Keep only middle z-layer
    patch_cells = patch_cells[keep2D[patch_cells]]

    # Restrict by minimum y if specified
    if y_min_phys is not None and np.isfinite(y_min_phys):
        patch_cells = patch_cells[yC[patch_cells] >= y_min_phys]

    return patch_cells

def get_run_up_sim(case_dir = '/nfs/home/geocean/alonsoap/projects/HyCFD/outputs/openfoam_cases_backup/0000', warm_up_time=0.0):

    mesh_dir = os.path.join(case_dir, 'constant', 'polyMesh')
    xC, yC, zC, nCells = get_cell_centers(mesh_dir)
    bottom_cells = select_patch_cells(mesh_dir, patch_name='bottom', zC=zC, yC=yC, y_min_phys=None)

    times = []
    ru = []

    time_dirs = list_time_dirs(case_dir)

    for t_dir in time_dirs:
        times.append(float(t_dir))

        alpha_file_path = os.path.join(case_dir, t_dir, 'alpha.water')

        if not os.path.isfile(alpha_file_path):
            continue

        # Read alpha.water file and compute run-up
        alpha = read_foam_internal_scalar(alpha_file_path, nCells)
        alpha_bottom = alpha[bottom_cells]

        alpha_water = alpha_bottom >= 0.5
        if np.any(alpha_water):
            y_water = yC[bottom_cells][alpha_water]
            ru.append(np.max(y_water))

        else:
            ru.append(np.nan)

    times = np.array(times)
    ru = np.array(ru)

    sort_idx = np.argsort(times)
    times = times[sort_idx]
    ru = ru[sort_idx]

    good = np.isfinite(times) & np.isfinite(ru)
    times = times[good]
    ru = ru[good]

    use = times >= warm_up_time
    ru_stats = ru[use]

    if ru_stats.size == 0:
        ru2 = np.nan
    else:
        ru2 = np.percentile(ru_stats, 98)

    return times, ru, ru2

def estimate_eta_column(y_col, alpha_col, alphaIso=0.5):
    """
    Estimate free surface along a single vertical column using linear interpolation.
    """
    # Remove NaNs
    mask = np.isfinite(y_col) & np.isfinite(alpha_col)
    y = y_col[mask]
    a = alpha_col[mask]
    if y.size < 2:
        return np.nan

    # Sort bottom -> top
    sort_idx = np.argsort(y)
    y = y[sort_idx]
    a = a[sort_idx]

    # Average alpha at duplicate y values (exact duplicates only)
    unique_y, inverse_idx = np.unique(y, return_inverse=True)
    alpha_avg = np.array([a[inverse_idx == i].mean() for i in range(len(unique_y))])

    # Find crossings of alphaIso
    s = alpha_avg - alphaIso
    cross_idx = np.where(s[:-1] * s[1:] <= 0)[0]
    if cross_idx.size == 0:
        # Fallback
        if np.mean(alpha_avg > alphaIso) > 0.8:
            return np.max(unique_y)
        else:
            return np.nan

    # Linear interpolation for each crossing
    eta_all = []
    for i in cross_idx:
        y1, y2 = unique_y[i], unique_y[i+1]
        a1, a2 = alpha_avg[i], alpha_avg[i+1]
        if np.abs(a2 - a1) < 1e-14:
            eta_all.append(0.5 * (y1 + y2))
        else:
            eta_all.append(y1 + (alphaIso - a1) * (y2 - y1) / (a2 - a1))

    return np.max(eta_all)


def get_free_surface(case_dir, deltaX=1.0, alpha_threshold=0.5):
    """
    Compute the free surface profile over time with sub-cell interpolation.
    """
    mesh_dir = os.path.join(case_dir, 'constant', 'polyMesh')
    xC, yC, zC, nCells = get_cell_centers(mesh_dir)

    time_dirs = list_time_dirs(case_dir)
    times = []
    fs_data = []

    x_min, x_max = xC.min(), xC.max()
    x_grid = np.arange(x_min, x_max + deltaX, deltaX)

    for t_dir in time_dirs:
        t_val = float(t_dir)
        times.append(t_val)

        alpha_file_path = os.path.join(case_dir, t_dir, 'alpha.water')
        if not os.path.isfile(alpha_file_path):
            fs_data.append(np.full_like(x_grid, np.nan))
            continue

        alpha = read_foam_internal_scalar(alpha_file_path, nCells)

        # --- Compute eta per vertical column ---
        fs_column = []
        unique_x = np.unique(xC)
        for xi in unique_x:
            mask = xC == xi
            eta = estimate_eta_column(yC[mask], alpha[mask], alphaIso=alpha_threshold)
            fs_column.append(eta)

        fs_column = np.array(fs_column)

        # --- Interpolate to regular x_grid ---
        fs_interp = np.interp(x_grid, unique_x, fs_column, left=np.nan, right=np.nan)
        fs_data.append(fs_interp)

    times = np.array(times)
    fs_data = np.array(fs_data)  # shape: n_times x n_x

    # --- Sort by time ---
    sort_idx = np.argsort(times)
    times = times[sort_idx]
    fs_data = fs_data[sort_idx, :]

    fs_xr = xr.Dataset(
        {
            "free_surface": (["time", "x"], fs_data)
        },
        coords={
            "time": times,
            "x": x_grid
        }
    )

    return times, fs_xr