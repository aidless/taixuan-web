# Mock payment warning

`alipay_mock.py` / `stripe_mock.py` sit next to real interfaces. Never import them in production code paths; CI does not enforce this yet. Production wiring must be reviewed against this file.
