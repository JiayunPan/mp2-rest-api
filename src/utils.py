import logging


def setup_logging(verbose: bool = False) -> None:
    """Configure application logging.

    verbose=True  -> DEBUG level (show everything)
    verbose=False -> INFO level
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )