# Langfuse Integration for Observability

Open LangGraph includes plug-and-play integration with [Langfuse](https://langfuse.com/) to provide detailed tracing and observability for your LangGraph executions. When enabled, all graph executions are traced and the logs are sent to your Langfuse project.

## Enabling Langfuse

To enable Langfuse, you'll need to configure a few environment variables. The recommended way is to create a `.env` file in the root of your project and add the following key-value pairs.

1. **Enable the Integration**: Set the following variable to `true` in your `.env` file:

    ```env
    LANGFUSE_LOGGING=true
    ```

2. **Configure Langfuse Credentials**: You'll also need to provide your Langfuse project credentials, which can be found in your Langfuse project settings. You can use [Langfuse Cloud](https://cloud.langfuse.com) or your own self-hosted instance.

    ```env
    LANGFUSE_PUBLIC_KEY="pk-lf-..."
    LANGFUSE_SECRET_KEY="sk-lf-..."
    LANGFUSE_HOST="https://cloud.langfuse.com" # Or your self-hosted instance URL
    ```

3. **Install Langfuse Package**: To use this integration, you need to have the `langfuse` Python package installed.

    ```bash
    pip install langfuse
    ```

    If `LANGFUSE_LOGGING` is enabled but the package is not installed, Open LangGraph will log a warning and continue to run without tracing.

## What's Traced

This integration is designed to be zero-config. When enabled, it will automatically capture and send the following metadata with every trace:

- **Session ID**: The `thread_id` of the conversation is automatically used as the `langfuse_session_id`. This groups all runs for the same thread into a single session in Langfuse.
- **User ID**: The `user.identity` is used as the `langfuse_user_id`, allowing you to filter traces by user.
- **Tags**: A default set of tags is automatically added to each trace to provide context:
  - `open_langgraph_run`: Identifies the trace as originating from the Open LangGraph server.
  - `run:<run_id>`: The specific ID of the run.
  - `thread:<thread_id>`: The thread ID.
  - `user:<user_id>`: The user ID.

This metadata-rich tracing allows you to easily debug issues, analyze performance, and understand how your agents are being used in the Langfuse UI.

- **Important**: You'll need to restart the server after making changes to your `.env` file.

## Future Improvements

- **Trace ID Correlation**: To make debugging even easier, we plan to set the Langfuse `trace_id` to be the same as the Open LangGraph `run_id`. This will allow for a direct one-to-one mapping between an execution in your system and its corresponding trace in Langfuse.

For more information on Langfuse and its features, please refer to the [official Langfuse documentation](https://langfuse.com/docs).
