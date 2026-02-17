## 🧪 Testing

This project includes a suite of unit and integration tests to ensure the server
functions correctly. The following commands should be run from the root of the
`gerrit` project.

### Running the Tests

1.  **Set up the test environment and install dependencies (if not already done):**
    ```bash
    python build.py
    ```
2.  **Run the tests:**
    ```bash
    python run_tests.py
    ```

This command will discover and run all tests in the `tests` directory.

### Making any changes to source

If any changes to source are ever made, you must run `python run_tests.py` to
validate that the changes did not break any tests. Ask the user first after any
changes are made.
