from __future__ import annotations

import os
import shutil
from pathlib import Path

import typer
from models.utils import get_paths
from pipeline.build_store import run_ingest
from pipeline.ingest import ingest_all
from features.build_features import build_feature_table
from models.train_if import train_model
from models.infer import score_features
from pipeline.alerting import select_alerts
from pipeline.bundle import build_bundles_for_top_alerts
from pipeline.run_demo import run_all

app = typer.Typer()

@app.command()
def ingest(reset: bool = typer.Option(False, "--reset", is_flag=True, help="Reset data before ingest")):
    """Ingest raw logs and convert to ECS Parquet format"""
    if reset:
        paths = get_paths()
        data_dir = Path(paths["ecs_parquet_dir"])
        if data_dir.exists():
            shutil.rmtree(data_dir)
            print(f"[reset] Removed {data_dir}")
    
    print("[ingest] Starting data ingestion...")
    ingest_all()
    print("[ingest] Ingestion completed!")

@app.command()
def featurize(reset: bool = typer.Option(False, "--reset", is_flag=True, help="Reset features before building")):
    """Build feature table from ECS data"""
    if reset:
        paths = get_paths()
        features_dir = Path(paths["features_dir"])
        if features_dir.exists():
            shutil.rmtree(features_dir)
            print(f"[reset] Removed {features_dir}")
    
    print("[featurize] Building features...")
    build_feature_table()
    print("[featurize] Feature building completed!")

@app.command()
def train(reset: bool = typer.Option(False, "--reset", is_flag=True, help="Reset model before training")):
    """Train Isolation Forest model"""
    if reset:
        paths = get_paths()
        models_dir = Path(paths["models_dir"])
        if models_dir.exists():
            shutil.rmtree(models_dir)
            print(f"[reset] Removed {models_dir}")
    
    print("[train] Training Isolation Forest...")
    train_model()
    print("[train] Model training completed!")

@app.command()
def score(reset: bool = typer.Option(False, "--reset", is_flag=True, help="Reset scores before scoring")):
    """Score anomalies using trained model"""
    if reset:
        paths = get_paths()
        scores_dir = Path(paths["scores_dir"])
        if scores_dir.exists():
            shutil.rmtree(scores_dir)
            print(f"[reset] Removed {scores_dir}")
    
    print("[score] Scoring anomalies...")
    score_features()
    print("[score] Scoring completed!")

@app.command()
def bundle():
    """Create forensic bundles for top alerts"""
    print("[bundle] Creating forensic bundles...")
    paths = get_paths()
    scores_path = Path(paths["scores_dir"]) / "scores.parquet"
    if not scores_path.exists():
        print("[bundle] No scores found. Run 'score' command first.")
        return
    
    top, thr = select_alerts(str(scores_path))
    build_bundles_for_top_alerts(top, thr)
    print("[bundle] Bundle creation completed!")

@app.command()
def demo(reset: bool = typer.Option(False, "--reset", is_flag=True, help="Reset data before demo")):
    """Run complete demo pipeline: ingest → featurize → train → score → bundle"""
    if reset:
        paths = get_paths()
        data_dir = Path(paths["ecs_parquet_dir"])
        features_dir = Path(paths["features_dir"])
        models_dir = Path(paths["models_dir"])
        scores_dir = Path(paths["scores_dir"])
        bundles_dir = Path(paths["bundles_dir"])
        
        for d in [data_dir, features_dir, models_dir, scores_dir, bundles_dir]:
            if d.exists():
                shutil.rmtree(d)
                print(f"[reset] Removed {d}")
    
    print("[demo] Running complete pipeline...")
    bundles_path = run_all()
    print(f"[demo] Pipeline completed! Bundles created in: {bundles_path}")

if __name__ == "__main__":
    app()