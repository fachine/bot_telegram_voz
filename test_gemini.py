import os
from ai_agent import agent
from dotenv import load_dotenv

load_dotenv()

def test_chat():
    print("--- Testando CHAT ---")
    question = "Quais são os procedimentos de limpeza?"
    response = agent.ask(question)
    print(f"Pergunta: {question}")
    print(f"Resposta: {response}")

def test_tts():
    print("\n--- Testando TTS ---")
    text = "Olá, esta é uma resposta de teste."
    output = "test_output.mp3"
    success = agent.tts(text, output)
    if success and os.path.exists(output):
        print("Sucesso! Arquivo test_output.mp3 gerado.")
        # os.remove(output)
    else:
        print("Falha ao gerar áudio.")

if __name__ == "__main__":
    if not agent.ready:
        print("Agente não está pronto!")
    else:
        test_chat()
        test_tts()
