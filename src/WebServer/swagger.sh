#!/bin/bash
# Execute swag init to generate Swagger documentation
swag init --parseDependency --parseInternal -g main.go -o ./docs

# Check command execution status
if [ $? -eq 0 ]; then
    echo "======================================"
    echo "Swagger documentation generated successfully!"
    echo "Output path: ./docs"
    echo "======================================"
else
    echo "======================================"
    echo "ERROR: Failed to generate Swagger documentation!"
    echo "Please verify:"
    echo "1. Is the 'swag' tool installed (run 'swag -v' to check)?"
    echo "2. Are the parameters (e.g., main.go path) correct?"
    echo "======================================"
    exit 1
fi