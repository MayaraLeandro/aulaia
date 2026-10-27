# AulaIA — protótipo completo (v0.2)

Aplicação web para celular: recebe um PDF, prepara um roteiro em cenas, gera narração feminina pt-BR e exporta um MP4 com cenas visuais e áudio sincronizado.

## Rodar
Requer Python 3.10+ e internet para voz e, opcionalmente, para a API de roteiro.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Depois, abra o endereço indicado pelo Streamlit. Para usar no celular, o computador e o celular podem estar na mesma rede Wi-Fi (configurar `--server.address 0.0.0.0`) ou o app pode ser hospedado em um serviço compatível com Streamlit.

## Como usar
1. Envie um PDF com texto selecionável.
2. (Opcional) Informe uma chave da API Gemini para gerar um roteiro didático com IA. A chave não é salva no app.
3. Clique em “Ler PDF e preparar roteiro”.
4. Revise títulos, narrações e descrições visuais.
5. Clique em “Gerar videoaula MP4” e baixe o resultado.

## Limitações honestas desta versão
- A versão gera cenas gráficas/infográficos a partir do texto; não gera fotos ou clipes de vídeo IA realistas.
- A voz feminina usa Edge TTS, um serviço online externo não oficial. Pode mudar, falhar ou ter termos alterados. Não há garantia de serviço gratuito permanente.
- A API Gemini é opcional e pode ter cotas/preços próprios. O app não inclui chave.
- PDF escaneado sem camada de texto exige OCR, ainda não incluído.
- Um vídeo de 30 minutos pode demorar e exigir memória no servidor.
- Não envie documentos confidenciais sem avaliar a privacidade do serviço onde o app estiver hospedado.

## Próximas melhorias
OCR para PDFs escaneados, busca de imagens licenciadas, transições animadas, legendas sincronizadas por frase e renderização em vertical 9:16.
