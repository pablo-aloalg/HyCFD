#!/bin/bash

CASE_DIR="$1"

source /opt/OpenFOAM/OpenFOAM-v1912/etc/bashrc

cd "$CASE_DIR" 

blockMesh # 1. Generate mesh
checkMesh # 2. Optional: check mesh quality
setWaveParameters # 3. Set wave parameters (if needed, depends on your waveProperties)
setWaveField # 4. Initialize wave field in 0/ folder
decomposePar # 5. Decompose per processor