from content_mvp.prefect_jobs import _build_flow


def main() -> None:
    flow = _build_flow()
    flow.serve(
        name="process-pending-urls-every-5m",
        interval=300,
        parameters={
            "limit": 1,
            "use_downie": True,
            "downie_wait": 180,
        },
    )


if __name__ == "__main__":
    main()
