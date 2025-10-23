import typer

app = typer.Typer(help="Loganom AI demo CLI")

def _safe_run_ingest():
    try:
        from pipeline.ingest import ingest_all
        ingest_all()
    except Exception:
        from pipeline.build_store import run_ingest
        run_ingest()

@app.command("ingest")
def cmd_ingest():
    _safe_run_ingest()
    typer.echo("[ingest] Done.")

@app.command("featurize")
def cmd_featurize():
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
def cmd_score():
    from models.infer import score_features
    out = score_features()
    typer.echo(f"[score] Wrote: {out}")

@app.command("demo")
def cmd_demo():
    cmd_ingest()
    cmd_featurize()
    cmd_train()
    cmd_score()

if __name__ == "__main__":
    app()