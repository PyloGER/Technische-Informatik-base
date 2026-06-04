import streamlit as st
import asyncio
import logging
from dataclasses import dataclass

@dataclass
class ChatMessage:
    role: str
    content: str
from src.chatbot import CustomChatBot
import os

INDEX_DATA = os.environ.get("INDEX_DATA", "0")
PULL_EMBEDDING_MODEL = os.environ.get("PULL_EMBEDDING_MODEL", "0")

# Configure logger
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more details
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console logs
    ],
)

logger = logging.getLogger(__name__)

def reset_messages():
    st.session_state["messages"] = [
        ChatMessage(role="assistant", content="Wie kann ich dir helfen?")
    ]

def init_bot() -> CustomChatBot | None:
    try:
        return CustomChatBot(
            index_data=bool(int(INDEX_DATA)),
            pull_embedding_model=bool(int(PULL_EMBEDDING_MODEL)),
        )
    except ValueError as e:
        logger.error(f"Invalid env variable: {e}")
        st.error(f"Configuration error: {e}")
    except ConnectionError as e:
        logger.error(f"Connection error during bot init: {e}")
        st.error("Could not connect to required services. Check your setup.")
    except Exception as e:
        logger.exception(f"Unexpected error during bot init: {e}")
        st.error(f"Failed to initialize chatbot: {e}")
    return None

if "bot" not in st.session_state:
    st.session_state["bot"] = init_bot()

if st.session_state.get("bot") is None:
    st.warning("Chatbot is unavailable. Please check logs and restart.")
    st.stop()

# Streamlit UI setup
st.set_page_config(page_title="ChatDoc", page_icon="📄")
st.header("Chat with your Document")

# Initialize session state
if "messages" not in st.session_state or not st.session_state["messages"]:
    reset_messages()

if st.sidebar.button("Clear message history"):
    reset_messages()

# Display chat messages
for msg in st.session_state.messages:
    st.chat_message(msg.role).write(msg.content)

# Handle user input
if user_query := st.chat_input(placeholder="Nachricht schreiben..."):
    st.session_state.messages.append(ChatMessage(role="user", content=user_query))
    logger.info(f"Write user message in session state {user_query}")
    st.chat_message("user").write(user_query)

    async def handle_user_query(user_query: str):
        container = st.empty()
        answer = ""
        try:
            async for chunk in st.session_state["bot"].astream(user_query):
                if chunk:
                    answer += chunk
                    container.markdown(answer)
        except asyncio.TimeoutError:
            logger.error("Query timed out.")
            container.error("Request timed out. Please try again.")
        except ConnectionError as e:
            logger.error(f"Connection error during streaming: {e}")
            container.error("Lost connection to the backend. Please retry.")
        except Exception as e:
            logger.exception(f"Unexpected error processing query: {e}")
            container.error(f"An unexpected error occurred: {e}")

        if answer:
            logger.info(f"Appending assistant response to session state.")
            st.session_state["messages"].append(
                ChatMessage(role="assistant", content=answer)
            )

    with st.chat_message("assistant"):
        with st.spinner("Searching documents and generating response..."):
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(handle_user_query(user_query))
            except RuntimeError as e:
                logger.error(f"Event loop error: {e}")
                st.error("Internal async error. Please restart the app.")
            finally:
                loop.close()