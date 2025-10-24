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


@app.command("train-lstm")
def cmd_train_lstm():
    from models.lstm_anomaly import train_lstm_model
    out = train_lstm_model()
    typer.echo(f"[train-lstm] Wrote: {out}")


@app.command("score-lstm")
def cmd_score_lstm():
    from models.lstm_infer import score_lstm_features
    out = score_lstm_features()
    typer.echo(f"[score-lstm] Wrote: {out}")


@app.command("ensemble")
def cmd_ensemble():
    from models.ensemble import combine_if_lstm
    out = combine_if_lstm()
    typer.echo(f"[ensemble] Wrote: {out}")


@app.command("respond")
def cmd_respond(apply: bool = typer.Option(False, help="Apply actions (otherwise dry-run)")):
    from pipeline.respond import respond
    out = respond(dry_run=not apply)
    typer.echo(f"[respond] Audit log: {out}")

@app.command("demo")
def cmd_demo():
    cmd_ingest()
    cmd_featurize()
    cmd_train()
    cmd_score()


@app.command("demo-lstm")
def cmd_demo_lstm():
    cmd_ingest()
    cmd_featurize()
    cmd_train_lstm()
    cmd_score_lstm()
    cmd_ensemble()

if __name__ == "__main__":
    app()