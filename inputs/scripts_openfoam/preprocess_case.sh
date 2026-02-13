#!/bin/bash

CASE_DIR="$1"

source /home/openfoam/OpenFOAM/openfoam-v1912/etc
cd "$CASE_DIR" 

#openFOAM Commands
blockMesh
setWaveParameters