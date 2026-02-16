#!/bin/bash

CASE_DIR="$1"

source /home/openfoam/OpenFOAM/openfoam-v1912/etc
cd "$CASE_DIR" 

reconstructPar -latestTime -fields "U alpha.water p_rgh zeta"
