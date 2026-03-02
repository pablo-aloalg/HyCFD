import os
import re

import numpy as np

def get_n_cells(case_dir: str): 
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