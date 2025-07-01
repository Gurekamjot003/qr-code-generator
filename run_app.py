import importlib.util
import sys

# Load user's app dynamically
USER_APP_FILE = "main.py"  # User's file
MODULE_NAME = "main"

spec = importlib.util.spec_from_file_location(MODULE_NAME, USER_APP_FILE)
main_app = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = main_app
spec.loader.exec_module(main_app)

# Check if the user has a Flask app instance
if hasattr(main_app, 'app'):
    main_app.app.run(host='0.0.0.0', port=3000)
else:
    print("Error: Flask app instance not found in main.py")