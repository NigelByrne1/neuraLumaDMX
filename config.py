"""Runtime settings: DMX interface, LLM endpoint, fixture addressing."""

# USB DMX / serial interface
interface_port = "COM3"
interface_baudrate = 57600

# llama.cpp (or compatible) OpenAI-style API
llm_port = "8033"
llm_url = "http://127.0.0.1:" + llm_port + "/v1/chat/completions"

# DMX start channel (1-based) for each of 4 RGBW fixtures — set fixtures to 4-channel RGBW mode
fixture_start_channels = [1, 5, 9, 13]
