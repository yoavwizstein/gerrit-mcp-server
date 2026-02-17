# Gemini CLI Configuration

You can configure the Gemini CLI to use this MCP server, allowing you to
interact with Gerrit directly from your terminal. The server can be installed as
a **Gemini Extension**, or run in **HTTP** or **STDIO** modes.

## Gemini Extension (recommended)

This method is recommended as it is easy and requires only one step. You do not
need to manually modify the Gemini settings file.

Run the following command:
```bash
gemini extension install <path-to-gerrit-mcp-server>
```

> Read more about Gemini extensions in [https://geminicli.com/docs/extensions/](https://geminicli.com/docs/extensions/).

## HTTP Mode

In HTTP mode, the server runs as a persistent background process. This is
recommended for frequent use.

1.  **Start the Server:**
    From the `gerrit-mcp-server` project directory, run:
    ```bash
    python server.py start
    ```

2.  **Configure Gemini CLI:**
    Add the following to your `$HOME/.gemini/settings.json` file. This tells the
    CLI to connect to the running HTTP server.

    ```json
    {
      "mcpServers": {
        "gerrit": {
          "httpUrl": "http://localhost:6322/mcp",
          "timeout": 15000
        }
      }
    }
    ```

## STDIO Mode

In STDIO mode, the Gemini CLI starts the MCP server on-demand for each request.
This is useful if you don't want a server running in the background.

**Configure Gemini CLI:** Add the following to your Gemini settings file. Make
sure to replace `<path_to_project>` with the absolute path to your
`gerrit-mcp-server` project directory.

*   **Settings file location:**
    *   Linux / macOS: `$HOME/.gemini/settings.json`
    *   Windows: `%USERPROFILE%\.gemini\settings.json`

**Linux / macOS:**
```json
{
  "mcpServers": {
    "gerrit": {
      "command": "<path_to_project>/.venv/bin/python",
      "args": [
        "<path_to_project>/gerrit_mcp_server/main.py",
        "stdio"
      ],
      "env": {
        "PYTHONPATH": "<path_to_project>/"
      }
    }
  }
}
```

**Windows:**
```json
{
  "mcpServers": {
    "gerrit": {
      "command": "<path_to_project>\\.venv\\Scripts\\python.exe",
      "args": [
        "<path_to_project>\\gerrit_mcp_server\\main.py",
        "stdio"
      ],
      "env": {
        "PYTHONPATH": "<path_to_project>\\"
      }
    }
  }
}
```

Now, when you run `gemini`, you can use the `@gerrit` tool directly.
