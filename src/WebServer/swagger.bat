@echo off

swag init --parseDependency --parseInternal -g main.go -o ./docs


if %errorlevel% equ 0 (
    echo ======================================
    echo Swagger documentation generated successfully!
    echo Output path: ./docs
    echo ======================================
) else (
    echo ======================================
    echo ERROR: Failed to generate Swagger documentation!
    echo Please check:
    echo 1. Is "swag" tool installed(run 'swag -v' to check)?
    echo 2. Are the parameters (e.g., main.go path) correct?
    echo ======================================
    pause
)