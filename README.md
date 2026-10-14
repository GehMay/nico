# Nico

> **Projeto pessoal de portfólio - todos os direitos reservados.** Este repositório está público
> apenas para leitura e avaliação (recrutadores, professores, colegas). **Não são aceitos Pull
> Requests, forks com intenção de reuso, nem qualquer uso, cópia ou redistribuição do código sem
> autorização por escrito da autora** - veja [`LICENSE`](LICENSE).

Assistente de voz local, em português, para Windows - um projeto pessoal/acadêmico de portfólio.

Nico escuta por palavra-chave ("Nico") ou duas palmas, entende comandos falados ou digitados,
responde com uma IA local (Ollama) com reforço opcional em nuvem (Groq, Gemini, Kimi), e tem
memória persistente de conversas, fatos e lembretes. Interface via uma janela HUD compacta
(pywebview) e um painel web (Flask) com galáxia de memória, transcript e controles.

## Principais recursos

- Ativação local por voz (Vosk) ou duas palmas, sem depender da nuvem para ouvir o nome.
- Transcrição de comando via Whisper local (`faster-whisper`), com fallback para Google Speech
  Recognition.
- Memória com busca por similaridade (SQLite + Jaccard), fatos lembrados sob pedido e lembretes
  com hora marcada.
- Agenda combinando lembretes próprios e eventos do Google Calendar (feed iCal, somente leitura).
- Clima, calculadora, controle de volume, abrir apps/sites, busca no YouTube, modos de trabalho.
- "Modo Pesquisa": busca na web e gera um relatório em PDF com referências.
- Geração de pequenos projetos de código via IA (Kimi), sempre numa pasta isolada e nunca
  executada automaticamente - o projeto não se auto-modifica.
- Dados pessoais (conversas, fatos, lembretes, perfil de voz) cifrados em repouso (AES/Fernet,
  chave protegida por DPAPI do Windows).

## Stack

Python 3.11, Flask, SQLite, Ollama, Vosk, faster-whisper, edge-tts, pywebview, vis-network.
Detalhes completos da arquitetura e do histórico de decisões estão em [`AGENTS.md`](AGENTS.md).

## Status

Projeto pessoal, considerado funcionalmente finalizado. O código está público para fins de
portfólio e avaliação técnica - não é um projeto open source ativo. Sinta-se à vontade para
explorar o código e abrir uma Issue com perguntas.

## Executando localmente

Requer Python 3.11, Ollama rodando localmente, e (opcionais) chaves de API gratuitas para Groq,
Gemini, Kimi, Tavily e um link iCal do Google Calendar - veja [`.env.example`](.env.example) e
[`COMANDOS_NICO.txt`](COMANDOS_NICO.txt) para o passo a passo.

```powershell
py -3.11 -m pip install -r requirements.txt
py -3.11 nico.py
```

## Licença

Todos os direitos reservados - veja [`LICENSE`](LICENSE). O código é disponibilizado apenas para
leitura/avaliação (ex.: portfólio, recrutamento); uso, cópia, modificação ou redistribuição não
são permitidos sem autorização.
