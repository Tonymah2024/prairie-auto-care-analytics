# Deploying to Streamlit Community Cloud

1. Push the repository to GitHub (the generated `data/synthetic`, `data/*.db` and `outputs/` folders must be committed - the app reads them; it does not rebuild the data).
2. On https://share.streamlit.io choose **New app**, select the repository and branch, main file `dashboard/app.py`, Python 3.11.
3. Requirements are read from `requirements.txt`; the theme from `.streamlit/config.toml`.
4. After the first start, open each of the 15 pages once and confirm there are no errors; only then publish the URL.
5. To refresh the data: run `python run_pipeline.py` locally and commit the regenerated outputs.

Local run: `pip install -r requirements.txt && streamlit run dashboard/app.py`.
PDF rendering in the pipeline uses a local Chrome / Edge; Excel verification of the integrated model uses Microsoft Excel on macOS when available (otherwise skipped).
