# Demo de Detecção de Ameaças com IA

Sistema de demonstração ao vivo que simula um SOC (Security Operations Center) com detecção de ataques em tempo real usando o modelo **Qwen, rodando localmente via LM Studio** como motor de inteligência artificial.

## Visão Geral

O projeto é composto por três serviços independentes:

| Serviço | Arquivo | Porta | Descrição |
|---|---|---|---|
| API (backend) | `api.py` | 8000 | Gera logs, gerencia estado e expõe endpoints de simulação |
| Dashboard | `dashboard.py` | 8501 | Tela do projetor — exibe logs, gráfico e alertas em tempo real |
| Controle | `controle.py` | 8502 | Painel do apresentador — acessado pelo celular |

A IA (Qwen via LM Studio) analisa os logs a cada ciclo, classifica o padrão e aciona automaticamente o estado de alerta no dashboard sem nenhuma regra hardcoded.