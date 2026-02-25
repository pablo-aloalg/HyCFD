import re
import numpy as np

def read_boundary_patches(boundary_file):
    with open(boundary_file, 'r') as f:
        lines = f.read().splitlines()

    patches = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines, comments, brackets, numbers
        if (
            not line
            or line.startswith('//')
            or line in ('(', ')', ';')
            or re.match(r'^\d+$', line)
        ):
            i += 1
            continue

        # Detect patch name (single token line)
        token = re.match(r'^([A-Za-z0-9_]+)$', line)
        if token:
            name = token.group(1)

            # Find next non-empty line
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1

            # Check if next line is "{"
            if j < len(lines) and lines[j].strip() == '{':
                ptype = "patch"  # default type
                k = j + 1

                while k < len(lines):
                    L = lines[k].strip()

                    # Extract type
                    if L.startswith('type'):
                        t = re.match(r'^type\s+([A-Za-z0-9_]+)\s*;', L)
                        if t:
                            ptype = t.group(1)

                    if L == '}':
                        break

                    k += 1

                patches.append({
                    "name": name,
                    "type": ptype
                })

                i = k + 1
                continue

        i += 1

    return patches

def write_openfoam_field(
    output_file,
    class_name,
    dims,
    internal_data,
    patches,
    field_name,
    location="0",
    force_nonuniform=False,
    tol=1e-12,
    alpha_inlet_patch_vals=None,
):
    """
    Python equivalent of your MATLAB writeOpenFOAMField.
    """

    internal_data = np.asarray(internal_data)

    with open(output_file, "w") as f:

        # ---- Header ----
        write_foam_header(f, class_name, field_name, location)

        dims_str = " ".join(str(d) for d in dims)
        f.write(f"dimensions      [{dims_str}];\n\n\n")

        # ---- internalField ----
        if internal_data.ndim == 1 or internal_data.shape[1] == 1:
            vec = internal_data.flatten()

            if not force_nonuniform and is_uniform_scalar(vec, tol):
                f.write(f"internalField   uniform {vec[0]:g};\n\n")
            else:
                write_internal_scalar_nonuniform(f, vec)

        else:
            mat = internal_data

            if not force_nonuniform and is_uniform_vector(mat, tol):
                v = mat[0]
                f.write(
                    f"internalField   uniform ({v[0]:g} {v[1]:g} {v[2]:g});\n\n"
                )
            else:
                write_internal_vector_nonuniform(f, mat)

        # ---- boundaryField ----
        write_boundary_field_like_template(
            f, field_name, patches, alpha_inlet_patch_vals
        )

        # ---- Footer ----
        write_foam_footer(f)

def write_foam_header(f, class_name, object_name, location_str):
    header = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\\\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\\\\\    /   O peration     | Version:  v1912                                 |
|   \\\\\\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\\\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       {class_name};
    location    "{location_str}";
    object      {object_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

"""
    f.write(header)

def write_foam_footer(f):
    f.write("\n\n// ************************************************************************* //\n")

def write_boundary_field_like_template(f, field_name, patches, alpha_inlet_patch_vals=None):
    """
    Write the boundaryField section of an OpenFOAM field file.

    Parameters
    ----------
    f : file object
        Open file for writing.
    field_name : str
        Field name (e.g., 'U', 'p_rgh', 'alpha.water')
    patches : list of dict
        Each dict has 'name' and 'type' keys
    alpha_inlet_patch_vals : array-like or dict, optional
        Scalar values for 'inlet' patch (only used for alpha fields)
    """
    f.write("boundaryField\n{\n")

    for p in patches:
        p_name = p['name']
        p_type = p['type']

        f.write(f"    {p_name}\n")
        f.write("    {\n")

        # 2D empty patch
        if p_type == 'empty':
            f.write("        type            empty;\n")
            f.write("    }\n")
            continue

        # Logic for specific patch names
        if p_name == 'atmosphere':
            if field_name == 'U':
                f.write("        type            pressureInletOutletVelocity;\n")
                f.write("        value           uniform (0 0 0);\n")
            elif field_name == 'p_rgh':
                f.write("        type            totalPressure;\n")
                f.write("        rho             rho;\n")
                f.write("        psi             none;\n")
                f.write("        gamma           1;\n")
                f.write("        p0              uniform 0;\n")
                f.write("        value           uniform 0;\n")
            elif field_name == 'alpha.water':
                f.write("        type            inletOutlet;\n")
                f.write("        inletValue      uniform 0;\n")
                f.write("        value           uniform 0;\n")
            else:
                f.write("        type            zeroGradient;\n")

        elif p_name == 'inlet':
            if field_name == 'U':
                f.write("        type            waveVelocity;\n")
                f.write("        refValue        uniform (0 0 0);\n")
                f.write("        refGradient     uniform (0 0 0);\n")
                f.write("        valueFraction   uniform 1;\n")
                f.write("        value           uniform (0 0 0);\n")
            elif field_name == 'p_rgh':
                f.write("        type            zeroGradient;\n")
                f.write("        value           uniform 0;\n")
            elif field_name == 'alpha.water':
                f.write("        type            waveAlpha;\n")
                if alpha_inlet_patch_vals is not None:
                    vals = list(alpha_inlet_patch_vals)
                    write_patch_scalar_list(f, 'refValue', vals, indent=8)
                    f.write("        refGradient     uniform 0;\n")
                    f.write("        valueFraction   uniform 1;\n")
                    write_patch_scalar_list(f, 'value', vals, indent=8)
                else:
                    f.write("        refValue        uniform 0;\n")
                    f.write("        refGradient     uniform 0;\n")
                    f.write("        valueFraction   uniform 1;\n")
                    f.write("        value           uniform 0;\n")
            else:
                f.write("        type            zeroGradient;\n")

        elif p_name == 'outlet':
            if field_name == 'U':
                f.write("        type            pressureInletOutletVelocity;\n")
                f.write("        value           uniform (0 0 0);\n")
            elif field_name == 'p_rgh':
                f.write("        type            zeroGradient;\n")
            elif field_name == 'alpha.water':
                f.write("        type            inletOutlet;\n")
                f.write("        inletValue      uniform 0;\n")
                f.write("        value           uniform 0;\n")
            else:
                f.write("        type            zeroGradient;\n")

        elif p_name == 'bottom':
            if field_name == 'U':
                f.write("        type            slip;\n")  # use noSlip if needed
            elif field_name == 'p_rgh':
                f.write("        type            zeroGradient;\n")
            elif field_name == 'alpha.water':
                f.write("        type            zeroGradient;\n")
            else:
                f.write("        type            zeroGradient;\n")

        else:
            # Default for other patches
            if field_name == 'U':
                f.write("        type            zeroGradient;\n")
                f.write("        value           uniform (0 0 0);\n")
            elif field_name == 'p_rgh':
                f.write("        type            zeroGradient;\n")
            elif field_name == 'alpha.water':
                f.write("        type            zeroGradient;\n")
            else:
                f.write("        type            zeroGradient;\n")

        f.write("    }\n")

    f.write("}\n")

def is_uniform_scalar(v, tol=1e-12):
    v = np.asarray(v)
    return np.all(np.abs(v - v.flat[0]) < tol)

def is_uniform_vector(M, tol=1e-12):
    """
    Check if all rows of a matrix M are the same within a tolerance.

    Parameters
    ----------
    M : array-like, shape (N, 3)
        Vector field data (e.g., velocity vectors per cell)
    tol : float
        Tolerance for comparison

    Returns
    -------
    bool
        True if all rows are equal to the first row within tol
    """
    M = np.asarray(M)
    if M.size == 0:
        return True
    # Compute absolute difference to the first row
    diff = np.abs(M - M[0, :])
    return np.all(diff < tol)

def write_internal_scalar_nonuniform(f, vec):
    """
    Write a nonuniform scalar internalField to an OpenFOAM file.

    Parameters
    ----------
    f : file object
        Open file for writing.
    vec : array-like
        Scalar values for each cell.
    """
    vec = list(vec)  # ensure iterable
    N = len(vec)

    f.write("internalField   nonuniform List<scalar>\n")
    f.write(f"{N}\n")
    f.write("(\n")
    for v in vec:
        f.write(f"{v:g}\n")
    f.write(")\n;\n\n")

def write_internal_vector_nonuniform(f, M):
    """
    Write a nonuniform vector internalField to an OpenFOAM file.

    Parameters
    ----------
    f : file object
        Open file for writing.
    M : array-like, shape (N, 3)
        Vector values for each cell.
    """
    M = np.asarray(M)
    N = M.shape[0]

    f.write("internalField   nonuniform List<vector>\n")
    f.write(f"{N}\n")
    f.write("(\n")
    for row in M:
        f.write(f"({row[0]:g} {row[1]:g} {row[2]:g})\n")
    f.write(")\n;\n\n")

def write_patch_scalar_list(f, key_name, vals, indent=8):
    """
    Write a nonuniform scalar list for a patch in OpenFOAM format.

    Parameters
    ----------
    f : file object
        Open file for writing.
    key_name : str
        The dictionary key name (e.g., 'refValue' or 'value').
    vals : array-like
        Scalar values for the patch.
    indent : int
        Number of spaces for indentation.
    """
    sp = ' ' * indent
    vals = list(vals)

    # Header
    f.write(f"{sp}{key_name:<15} nonuniform List<scalar> \n")
    f.write(f"{len(vals)}\n")
    f.write("(\n")

    # Values
    for v in vals:
        f.write(f"{v:g}\n")

    # Footer
    f.write(")\n;\n")