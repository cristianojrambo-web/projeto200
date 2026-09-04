"""
Esteira de Propostas — leitor da pasta de rede.

Roda periodicamente (agendado no Task Scheduler do Windows) numa máquina com
acesso à pasta onde os corretores salvam os PDFs das propostas. Para cada PDF
ainda não visto, cria um card na aba "Propostas" do CRM Seguros — sem número
nem segurado preenchidos, já que o nome do arquivo não segue um padrão fixo.
A secretária completa esses dados na tela.

Não lê o conteúdo do PDF, não apaga nada da pasta e não sabe nada sobre
leads/clientes/atividades do CRM — só cria e mantém linhas na tabela
propostas_esteira via a REST API do Supabase, usando a service role key
(precisa dela para não esbarrar na regra de RLS que restringe a tabela a
gestor/secretaria logados).

Configuração via variáveis de ambiente (veja .env.example):
  PASTA_PROPOSTAS       caminho da pasta de rede com os PDFs (ex: \\\\SERVIDOR\\Propostas)
  SUPABASE_URL          URL do projeto Supabase (a mesma do index.html)
  SUPABASE_SERVICE_KEY  service_role key do Supabase — NUNCA a anon key, e NUNCA commitar
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PASTA_PROPOSTAS = os.environ.get("PASTA_PROPOSTAS", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
REDE_USUARIO = os.environ.get("REDE_USUARIO", "").strip()
REDE_SENHA = os.environ.get("REDE_SENHA", "").strip()


def garantir_conexao_rede():
    """Autentica no compartilhamento antes de ler a pasta — necessário quando o
    script roda agendado, sem a sessão do Windows já ter feito login lá antes
    (ex: logo após reiniciar, ou rodando como outro usuário)."""
    if not REDE_USUARIO or not PASTA_PROPOSTAS.startswith("\\\\"):
        return
    m = re.match(r"(\\\\[^\\]+)", PASTA_PROPOSTAS)
    if not m:
        return
    servidor = m.group(1)
    subprocess.run(["net", "use", servidor, "/delete", "/y"], capture_output=True, text=True)
    resultado = subprocess.run(
        ["net", "use", servidor, f"/user:{REDE_USUARIO}", REDE_SENHA],
        capture_output=True, text=True,
    )
    if resultado.returncode != 0:
        print(f"Aviso: não consegui autenticar em {servidor}: {resultado.stdout.strip()} {resultado.stderr.strip()}")


def checar_config():
    faltando = [nome for nome, valor in [
        ("PASTA_PROPOSTAS", PASTA_PROPOSTAS),
        ("SUPABASE_URL", SUPABASE_URL),
        ("SUPABASE_SERVICE_KEY", SUPABASE_SERVICE_KEY),
    ] if not valor]
    if faltando:
        print(f"Faltam variáveis de ambiente: {', '.join(faltando)}. Veja .env.example.")
        sys.exit(1)
    garantir_conexao_rede()
    if not Path(PASTA_PROPOSTAS).is_dir():
        print(f"Pasta não encontrada ou sem acesso: {PASTA_PROPOSTAS}")
        sys.exit(1)


def listar_pdfs(pasta: str):
    base = Path(pasta)
    return [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"]


def registrar_arquivo(nome: str, caminho_relativo: str) -> str:
    """Insere um card novo. 'ja_existia' se o arquivo já estava cadastrado, 'criado' se inseriu."""
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/propostas_esteira",
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={
            "arquivo_nome": nome,
            "arquivo_caminho": caminho_relativo,
            "status": "para_lancar",
        },
        timeout=30,
    )
    if resp.status_code in (200, 201):
        return "criado"
    if resp.status_code == 409:  # unique constraint em arquivo_nome — já registrado antes
        return "ja_existia"
    raise RuntimeError(f"Falha ao registrar {nome}: {resp.status_code} {resp.text}")


def main():
    checar_config()
    arquivos = listar_pdfs(PASTA_PROPOSTAS)
    criados = 0
    ja_existiam = 0
    erros = 0
    for caminho in arquivos:
        relativo = str(caminho.relative_to(PASTA_PROPOSTAS))
        try:
            resultado = registrar_arquivo(caminho.name, relativo)
            if resultado == "criado":
                criados += 1
                print(f"novo: {relativo}")
            else:
                ja_existiam += 1
        except Exception as exc:
            erros += 1
            print(f"erro em {relativo}: {exc}")

    print(f"Fim: {len(arquivos)} PDF(s) na pasta · {criados} novo(s) · {ja_existiam} já cadastrado(s) · {erros} erro(s)")


if __name__ == "__main__":
    main()
