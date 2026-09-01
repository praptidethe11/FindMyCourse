# CourseMatch

A simple frontend + backend around your course recommender. No new training happens here — this just serves the model you already trained in Colab.

```
course-recommender-app/
├── backend/
│   ├── main.py            FastAPI app — loads your Colab artifacts, exposes /recommend
│   ├── requirements.txt
│   └── data/              <- put the 4 files from Drive here (see step 1)
└── frontend/
    ├── index.html
    ├── styles.css
    └── script.js
```

## Step 1 — Get your Colab data onto your machine

You don't need the whole `course_recommender_data` Drive folder — only 4 files are needed for the running app (the raw dataset zips, `mincut_gcn_model.pt`, and `course_graph_edges.csv` were only needed for training/eval, not for serving recommendations):

- `unified_courses.csv`
- `course_embeddings.npy`
- `contrastive_embeddings.npy`
- `node_index_with_clusters.csv`

**Easiest way:** open [Google Drive](https://drive.google.com) in your browser, go into `course_recommender_data`, select those 4 files (Ctrl/Cmd-click each), right-click → **Download**. Drive zips just those files together. Unzip and drop all 4 into `backend/data/`.

## Step 2 — Run the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # on Windows Git Bash: source venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

First run downloads the `all-MiniLM-L6-v2` model (~90MB, one-time, free, no API key). You should see `[startup] Ready. 20103 courses loaded.` in the terminal. Leave this running.

Check it worked: open `http://localhost:8000/health` in a browser — should show `{"status":"ok","courses_loaded":20103,"hybrid_ranking":true}`.

## Step 3 — Open the frontend

Just open `frontend/index.html` directly in your browser (double-click it, or right-click → Open with browser). No build step, no server needed for the frontend itself.

Fill in the form and hit **Find courses** — it calls your local backend at `localhost:8000` and shows the top 5 matches.

## If something doesn't connect

The status area in the results panel will tell you plainly if it can't reach the backend — check the backend terminal is still running and that nothing else is using port 8000. If you ever host the backend somewhere other than your own machine, update `API_BASE` at the top of `frontend/script.js` to match.
