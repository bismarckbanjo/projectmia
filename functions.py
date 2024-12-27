# functions.py

def get_generate_responses_schema():
    """
    Returns the schema for the generate_multiple_responses function.
    This schema describes how the assistant should generate two responses:
    1. An acknowledgment of the user's input.
    2. A follow-up response to continue the conversation.
    """
    return [
        {
            "name": "generate_multiple_responses",
            "description": "Generate two responses for a single user input.",
            "parameters": {
                "type": "object",
                "properties": {
                    "acknowledgement": {
                        "type": "string",
                        "description": "Acknowledgement of the input."
                    },
                    "follow_up": {
                        "type": "string",
                        "description": "Follow-up response."
                    }
                },
                "required": ["acknowledgement", "follow_up"]
            }
        }
    ]
