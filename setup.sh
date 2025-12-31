#!/bin/bash

# Set up paths.
REPO_RELATIVE_PATH="$(dirname "${BASH_SOURCE[0]}")"
REPO_PATH=$(realpath "$REPO_RELATIVE_PATH")
SCRIPT_NAME='edit_rebase_todo.sh'

# Create edit_rebase_todo.sh script.
echo '#!/bin/bash' > $SCRIPT_NAME
echo '' >> $SCRIPT_NAME
echo '# This bash script runs edit_rebase_todo.py with a specified python' >> $SCRIPT_NAME
echo '# executable.' >> $SCRIPT_NAME
echo '' >> $SCRIPT_NAME
echo '# Replace these with absolute paths to your repo and the python' >> $SCRIPT_NAME
echo "# executable you want to use. They default to this script's parent" >> $SCRIPT_NAME
echo '# directory, and a virtual environment called venv in this directory.' >> $SCRIPT_NAME
echo "REPO_PATH=\"$REPO_PATH\"" >> $SCRIPT_NAME
echo "PYTHON_PATH=\"${VIRTUAL_ENV:-REPO_PATH/venv}/bin/python\"" >> $SCRIPT_NAME
echo '' >> $SCRIPT_NAME
echo "\$PYTHON_PATH \$REPO_PATH/edit_rebase_todo.py \$*" >> $SCRIPT_NAME

# Make script executable.
chmod +x $SCRIPT_NAME
