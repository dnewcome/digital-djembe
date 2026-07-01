# digital-djembe — Track B (planar magnetic head driver) tooling
#
#   make interactive   launch the MuJoCo membrane bench (glfw window):
#                      sliders for gap, strike force, coil current
#   make selftest      headless build + step + f0 calibration check
#   make render        headless gif of a strike vs the magnet gap -> build/
#
#   make coil          generate the 8-coil flex geometry + electrical report
#   make preview       render the coil layout to coil/coil_preview.png
#   make bl            magnetostatic BL sim (real force factor, the fab gate)
#   make gap           nonlinear FDTD head-deflection (gap clearance)
#   make deps          install python deps

PY  := python3
SIM := sim/membrane_sim.py

.PHONY: interactive selftest massload render modes coil preview bl gerber verify field holder gap gap-lin deps clean

interactive:
	MUJOCO_GL=glfw $(PY) $(SIM) --interactive

selftest:
	MUJOCO_GL=osmesa $(PY) $(SIM) --selftest

massload:
	MUJOCO_GL=osmesa $(PY) $(SIM) --massload

render:
	MUJOCO_GL=osmesa $(PY) $(SIM) --render

modes:
	MUJOCO_GL=osmesa $(PY) $(SIM) --modes

coil:
	$(PY) coil/coil_gen.py

preview: coil
	inkscape coil/coil_preview.svg -w 900 -o coil/coil_preview.png 2>/dev/null

bl:
	$(PY) coil/bl_sim.py

gerber:
	$(PY) coil/gerber_export.py

verify:
	$(PY) coil/verify_coil.py

field:
	$(PY) coil/field_map.py

holder:
	$(PY) cad/magnet_holder.py

gap:
	$(PY) coil/gap_fdtd.py

gap-lin:
	$(PY) coil/gap_sim.py

deps:
	$(PY) -m pip install mujoco numpy scipy matplotlib magpylib imageio

clean:
	rm -rf build sim/__pycache__ coil/__pycache__
