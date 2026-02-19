#!/bin/bash

CASE_DIR="$1"

source /opt/OpenFOAM/OpenFOAM-v1912/etc/bashrc

cd "$CASE_DIR" 

reconstructPar -fields '(U alpha.water p_rgh zeta)'
foamToVTK