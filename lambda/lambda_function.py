# -*- coding: utf-8 -*-

# Alexa skill that forwards what the user says to Claude and speaks the answer back.
# Built with the Alexa Skills Kit SDK for Python and the Anthropic Python SDK.
import logging
import os
import re
from xml.sax.saxutils import escape

import anthropic
import ask_sdk_core.utils as ask_utils

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Haiku: fast enough for Alexa's ~8s window and ~40x cheaper than Opus.
MODEL = "claude-haiku-5-5"
# Alexa waits ~8 seconds for a response, so keep the call short and never retry.
CLAUDE_TIMEOUT_SECONDS = 7.0
MAX_TOKENS = 1024
# Conversation is kept in session attributes; start over once it gets this long
# (Alexa caps the whole response payload at ~24 KB).
MAX_TURNS = 6

SYSTEM_PROMPT = (
    "Você é o Assistente Chat, um assistente de voz rodando numa Alexa. "
    "Responda sempre em português do Brasil, de forma curta e natural para ser falada em voz alta: "
    "no máximo três ou quatro frases. Não use markdown, listas, emojis, links ou código. "
    "Se a pergunta exigir uma resposta longa, dê um resumo. Não termine com perguntas para o usuário."
)

# TODO: send a summary of the conversation by email ("me manda por email o resumo").
#   - Give Claude an `enviar_email` tool so it detects the request and writes the summary itself.
#   - Send via Gmail SMTP (smtplib) with an app password, kept in a gitignored file like the API key.
#   - Recipient: fixed address in config (or Alexa Customer Profile API with alexa::profile:email:read).
#   - History only lives in the session; persist it to S3 (included in Alexa-hosted) to summarize past sessions.
#   - Summary + send must fit in Alexa's ~8s window; use a progressive response ("enviando...") if needed.

# TODO: answer "quanto eu gastei" by voice.
#   - Add up response.usage (input/output tokens) per call and persist the totals in S3.
#   - New intent that speaks total tokens and estimated cost (MODEL price table).
#   - Only counts this skill's usage; credit balance has no API, it's only shown in the Claude Console.
#   - Real org-wide usage/cost needs the Admin API (sk-ant-admin key, organization accounts only).

ANSWER_PREFIX = "Assistente Chat disse o seguinte: "
KEY_FILE = os.path.join(os.path.dirname(__file__), "anthropic_key.txt")


def _load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip()
    try:
        with open(KEY_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


client = anthropic.Anthropic(
    api_key=_load_api_key(),
    timeout=CLAUDE_TIMEOUT_SECONDS,
    max_retries=0,
)


def _to_speech(text):
    """Strip markdown leftovers and escape characters that break SSML."""
    text = re.sub(r"[*_#`>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return escape(text)


def ask_claude(handler_input, question):
    """Send the question (plus the session's history) to Claude and return the spoken answer."""
    session = handler_input.attributes_manager.session_attributes
    history = session.get("history", [])
    if len(history) >= MAX_TURNS * 2:
        history = []

    history.append({"role": "user", "content": question})

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=history,
        # Sent as a raw body field so this works on any SDK version the runtime installs.
        extra_body={"output_config": {"effort": "low"}},
    )

    if response.stop_reason == "refusal":
        session["history"] = history[:-1]
        return "Desculpe, não posso ajudar com isso."

    answer = " ".join(b.text for b in response.content if b.type == "text").strip()

    # Keep the full assistant content (including thinking blocks) so the next turn replays it unchanged.
    history.append({
        "role": "assistant",
        "content": [b.model_dump(exclude_none=True) for b in response.content],
    })
    session["history"] = history

    answer = _to_speech(answer)
    if not answer:
        return "Hmm, não consegui pensar em uma resposta."
    # Spoken prefix so it's clear the answer came from Claude, not Alexa's own search.
    return ANSWER_PREFIX + answer


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Oi, aqui é o Assistente Chat. O que você quer saber?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class ChatIntentHandler(AbstractRequestHandler):
    """Handler for free-form questions, forwarded to Claude."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("ChatIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        question = ask_utils.get_slot_value(handler_input, "pergunta")
        if not question:
            speak_output = "Não entendi a pergunta. Pode repetir?"
            return handler_input.response_builder.speak(speak_output).ask(speak_output).response

        try:
            speak_output = ask_claude(handler_input, question)
        except anthropic.APITimeoutError:
            logger.warning("Claude timed out")
            speak_output = "O Claude demorou demais para responder. Tente uma pergunta mais curta."
        except anthropic.AuthenticationError:
            logger.error("Invalid or missing Anthropic API key")
            speak_output = "A chave da API do Claude não está configurada corretamente."
        except anthropic.RateLimitError:
            speak_output = "O Claude está ocupado agora. Tente de novo em alguns segundos."
        except anthropic.APIStatusError as e:
            logger.error("Claude API error %s: %s", e.status_code, e.message)
            speak_output = "Tive um problema ao falar com o Claude. Tente de novo."
        except anthropic.APIConnectionError:
            logger.error("Could not reach Claude API", exc_info=True)
            speak_output = "Não consegui me conectar ao Claude. Tente de novo."

        # No reprompt: answer and end the session, like built-in Alexa commands.
        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_should_end_session(True)
                .response
        )


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Faça uma pergunta começando com, por exemplo, me diga, o que é, ou como. O que você quer saber?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Até mais!"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

class FallbackIntentHandler(AbstractRequestHandler):
    """Single handler for Fallback Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")
        speech = "Não entendi. Tente começar com me diga, ou o que é. O que você quer saber?"
        reprompt = "Não ouvi direito. O que você quer saber?"

        return handler_input.response_builder.speak(speech).ask(reprompt).response

class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "Você acionou " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Desculpe, tive um problema. Tente de novo."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(ChatIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
