import typer
from pathlib import Path
import shutil

app = typer.Typer(help="Loganom AI demo CLI")

def _safe_run_ingest():
    try:
        from pipeline.ingest import ingest_all
        ingest_all()
    except Exception:
        from pipeline.build_store import run_ingest
        run_ingest()

def _reset_dirs(*dirs: str):
    for d in dirs:
        p = Path(d)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            print(f"[reset] Removed {p}")

@app.command("ingest")
def cmd_ingest(reset: bool = typer.Option(False, help="Remove ECS Parquet before ingest")):
    if reset:
        _reset_dirs("data/ecs_parquet")
    _safe_run_ingest()
    typer.echo("[ingest] Done.")

@app.command("featurize")
def cmd_featurize(reset: bool = typer.Option(False, help="Remove features before building")):
    if reset:
        _reset_dirs("data/features")
    import features.build_features as bf
    func = getattr(bf, "build_feature_table", None) or getattr(bf, "build_feature_table_large", None)
    if not func:
        raise RuntimeError("No build_feature_table(_large) found in features.build_features")
    func()
    typer.echo("[featurize] Done.")

@app.command("train")
def cmd_train():
    from models.train_if import train_model
    train_model()
    typer.echo("[train] Done.")

@app.command("score")
def cmd_score(reset: bool = typer.Option(False, help="Remove scores before scoring")):
    if reset:
        _reset_dirs("data/scores")
    from models.infer import score_features
    out = score_features()
    typer.echo(f"[score] Wrote: {out}")

@app.command("train-lstm")
def cmd_train_lstm():
    from models.lstm_anomaly import train_lstm_model
    out = train_lstm_model()
    typer.echo(f"[train-lstm] Wrote: {out}")

@app.command("score-lstm")
def cmd_score_lstm(reset: bool = typer.Option(False, help="Remove LSTM scores before scoring")):
    if reset:
        _reset_dirs("data/scores_lstm", "data/scores/ensemble")
    from models.lstm_infer import score_lstm_features
    out = score_lstm_features()
    typer.echo(f"[score-lstm] Wrote: {out}")

@app.command("ensemble")
def cmd_ensemble(reset: bool = typer.Option(False, help="Remove ensemble scores before combining")):
    if reset:
        _reset_dirs("data/scores/ensemble")
    from models.ensemble import combine_if_lstm
    out = combine_if_lstm()
    typer.echo(f"[ensemble] Wrote: {out}")

@app.command("respond")
def cmd_respond(apply: bool = typer.Option(False, help="Apply actions (otherwise dry-run)")):
    from pipeline.respond import respond
    out = respond(dry_run=not apply)
    typer.echo(f"[respond] Audit log: {out}")

@app.command("demo")
def cmd_demo(reset: bool = typer.Option(False, help="Reset ecs/features/scores/bundles before run")):
    if reset:
        _reset_dirs("data/ecs_parquet", "data/features", "data/scores", "data/bundles")
    cmd_ingest(reset=False)
    cmd_featurize(reset=False)
    cmd_train()
    cmd_score(reset=False)

@app.command("demo-lstm")
def cmd_demo_lstm(reset: bool = typer.Option(False, help="Reset ecs/features/scores before run (LSTM path)")):
    if reset:
        _reset_dirs("data/ecs_parquet", "data/features", "data/scores", "data/bundles", "data/scores_lstm", "data/scores/ensemble")
    cmd_ingest(reset=False)
    cmd_featurize(reset=False)
    cmd_train_lstm()
    cmd_score_lstm(reset=False)
    cmd_ensemble(reset=False)

if __name__ == "__main__":
    app()