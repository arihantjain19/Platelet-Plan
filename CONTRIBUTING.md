# Contributing to PlateletPlan

Thanks for helping reduce platelet waste.

## Getting started
1. Fork the repository and create a branch: `git checkout -b feature/short-name`
2. `pip install -r requirements.txt`
3. Make your change, and add or update a test in `test_simulate.py`
4. Run `python -m pytest -q test_simulate.py`. If you changed the model or simulator, also run `python pp_pipeline.py` and report how `evaluation_test_year.csv` changed in your pull request.
5. Open a pull request describing **what** changed and **why**.

## Ground rules
- Every new parameter goes in `pp_config.py`, with a comment saying whether it is sourced (give the reference) or an ASSUMPTION.
- Never present synthetic results as real-world results.
- Never commit patient-identifiable data. Registers must be aggregated daily counts only.

## Good first issues
- Outbreak mode: raise the safety factor automatically when reported dengue cases rise fast
- ABO/Rh blood groups in the stock model
- OpenStreetMap/OpenRouteService travel times instead of straight-line estimates
- Loader for e-RaktKosh stock exports
- Test on a real centre's anonymised register (please get in touch)
