import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
FAISS_INDEX_PATH = os.path.join(OUTPUT_DIR, "faiss_index")

class AIAgent:
    def __init__(self):
        try:
            self.embeddings = OpenAIEmbeddings()
            self.vectorstore = FAISS.load_local(FAISS_INDEX_PATH, self.embeddings, allow_dangerous_deserialization=True)
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 4})
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.ready = True
        except Exception as e:
            print(f"Erro ao inicializar IA: {e}")
            self.ready = False

    def ask(self, question: str) -> str:
        if not self.ready:
            return "Desculpe, a base de conhecimento ainda não foi processada ou a IA não está configurada corretamente."
        
        try:
            # 1. Recuperar contexto do FAISS
            docs = self.retriever.invoke(question)
            context = "\n\n---\n\n".join([doc.page_content for doc in docs])
            
            # 2. Prompt do sistema
            system_prompt = (
                "Você é um assistente virtual de RH e Operações para um condomínio. "
                "Use os seguintes trechos de contexto recuperados dos POPs (Procedimentos Operacionais Padrão) e documentos internos para responder à pergunta do funcionário. "
                "Se você não souber a resposta ou ela não estiver no contexto, diga que não encontrou a informação nos documentos oficiais. "
                "Sempre responda em português, de forma clara, educada e direta.\n\n"
                f"Contexto:\n{context}"
            )
            
            # 3. Chamar OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.2
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Ocorreu um erro ao processar sua pergunta: {e}"

agent = AIAgent()
