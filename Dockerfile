# Usar uma imagem base leve de Python
FROM python:3.12-slim

# Instalar dependências do sistema
USER root
RUN apt-get update && apt-get install -y \
    libreoffice-common \
    libreoffice-writer \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Criar um usuário para o Hugging Face (segurança)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Definir diretório de trabalho
WORKDIR /home/user/app

# Copiar arquivos de dependências
COPY --chown=user requirements.txt .

# Instalar dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante do código
COPY --chown=user . .

# Criar pastas de dados e garantir permissões
RUN mkdir -p data/pdfs

# Comando para rodar o bot (unificado)
CMD python main.py
