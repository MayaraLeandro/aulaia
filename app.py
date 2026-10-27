import streamlit as st
import os, re, json, tempfile, subprocess, shutil, textwrap
from pathlib import Path

st.set_page_config(page_title="AulaIA", page_icon="🎓", layout="wide")
st.markdown("""
<style>
.stApp {background: #10131c; color: #f5f6fa;}
section[data-testid="stSidebar"] {background:#171b28;}
h1,h2,h3 {color:#ff6f9f;}
div.stButton > button {background:#ff4f91;color:white;border:0;border-radius:12px;font-weight:700;}
div[data-testid="stFileUploader"] {border:1px dashed #ff6f9f;border-radius:12px;padding:10px;}
</style>
""", unsafe_allow_html=True)

st.title("🎓 AulaIA")
st.caption("Transforme uma apostila em uma videoaula com roteiro, voz feminina, cenas e legendas.")
st.info("Esta versão gera um MP4 no servidor onde estiver instalada. Para usar pelo celular, publique o app em um serviço de hospedagem compatível.")

with st.sidebar:
    st.header("Configurações")
    duration = st.select_slider("Duração aproximada", options=[5,10,15,20,30,45,60], value=30, format_func=lambda x: f"{x} minutos")
    voice = st.selectbox("Voz feminina (português do Brasil)", ["Francisca — natural", "Thalita — natural"])
    style = st.selectbox("Estilo visual", ["Aula moderna com cartões e diagramas", "Quadro didático", "Apresentação profissional"])
    api_key = st.text_input("Chave Gemini (opcional)", type="password", help="Usada para criar um roteiro detalhado. Você pode testar sem chave com roteiro automático básico.")
    st.caption("A chave fica apenas nesta sessão e não é salva pelo app.")

uploaded = st.file_uploader("1. Envie sua apostila em PDF", type=["pdf"])
topic = st.text_input("Tema da aula (opcional)", placeholder="Ex.: Pensamento computacional: modelagem de soluções")
extra = st.text_area("Orientações adicionais (opcional)", placeholder="Explique o nível da turma, exemplos que deseja incluir...", height=90)

def extract_pdf(upload):
    try:
        from pypdf import PdfReader
        reader = PdfReader(upload)
        pages = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            if txt.strip():
                pages.append(f"[Página {i+1}]\\n{txt}")
        return "\\n\\n".join(pages)
    except Exception as e:
        raise RuntimeError(f"Não consegui ler o PDF: {e}")

def make_script(text, topic, duration, extra, api_key):
    if api_key:
        import requests
        prompt = f"""Crie um roteiro de videoaula em português brasileiro com duração aproximada de {duration} minutos, baseado EXCLUSIVAMENTE no material fornecido. Não invente afirmações que o material não apoie. Tema: {topic or 'identifique no documento'}. Orientações: {extra or 'explicação didática e detalhada'}.
Retorne SOMENTE JSON válido neste formato:
{{"title":"título","scenes":[{{"heading":"título curto","narration":"texto de narração completo, natural, com pontuação","visual":"descrição visual concreta para um slide/ilustração","keywords":["palavra 1","palavra 2"]}}]}}
Crie cenas suficientes para a duração solicitada, cada uma com cerca de 20-45 segundos de narração. Inclua exemplos, transições e revisão final. Use entre 8 e 30 cenas.
MATERIAL:
{text[:70000]}"""
        r = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            params={"key": api_key},
            json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"responseMimeType":"application/json","temperature":0.4}},
            timeout=180)
        r.raise_for_status()
        raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        match = re.search(r"\{.*\}", raw, re.S)
        if not match: raise ValueError("A IA não retornou JSON válido.")
        data = json.loads(match.group(0))
        if not data.get("scenes"): raise ValueError("O roteiro não contém cenas.")
        return data
    # Offline fallback: make scenes from the PDF paragraphs; useful for testing pipeline, not an AI-written lesson.
    paras = [re.sub(r"\s+"," ",p).strip() for p in re.split(r"\n{2,}|(?<=[.!?])\s{2,}", text) if len(p.strip()) > 100]
    if not paras:
        paras = [re.sub(r"\s+"," ",text).strip()]
    target = max(8, min(24, duration))
    groups = []
    per = max(1, len(paras)//target)
    for i in range(0, len(paras), per):
        chunk = " ".join(paras[i:i+per])
        if len(chunk) > 1800:
            chunk = chunk[:1800]
        if chunk:
            groups.append(chunk)
        if len(groups) >= target: break
    scenes=[]
    for i, p in enumerate(groups):
        scenes.append({"heading": f"Parte {i+1}", "narration": p, "visual": "Cartão didático com título, formas geométricas e palavras-chave relacionadas ao tema", "keywords": []})
    return {"title": topic or "Videoaula baseada na apostila", "scenes": scenes}

def make_tts(text, voice_name, out_path):
    import asyncio, edge_tts
    voice_id = "pt-BR-FranciscaNeural" if voice_name.startswith("Francisca") else "pt-BR-ThalitaNeural"
    async def run():
        comm = edge_tts.Communicate(text, voice_id, rate="-5%", volume="+0%")
        await comm.save(str(out_path))
    asyncio.run(run())

def wrap_words(text, max_chars=48):
    words = text.split()
    lines, line = [], ""
    for w in words:
        if len(line)+len(w)+1 > max_chars:
            lines.append(line); line=w
        else: line=(line+" "+w).strip()
    if line: lines.append(line)
    return lines

def build_video(data, voice_name, style, out_mp4, progress):
    from PIL import Image, ImageDraw, ImageFont
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
    import edge_tts
    work = Path(tempfile.mkdtemp(prefix="aulaia_"))
    clips=[]
    try:
        try:
            title_font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            body_font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 29)
            small_font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            title_font=body_font=small_font=ImageFont.load_default()
        total=len(data["scenes"])
        for i, scene in enumerate(data["scenes"]):
            progress.progress((i+1)/total, text=f"Gerando narração e cena {i+1} de {total}...")
            aud=work/f"audio_{i:03d}.mp3"
            make_tts(scene.get("narration",""), voice_name, aud)
            audio=AudioFileClip(str(aud))
            W,H=1280,720
            img=Image.new("RGB",(W,H),(16,20,33))
            d=ImageDraw.Draw(img)
            # decorative shapes
            d.rounded_rectangle((48,48,W-48,H-48), radius=30, outline=(255,79,145), width=4)
            d.ellipse((W-240,60,W-90,210), fill=(47,78,132))
            d.ellipse((W-190,100,W-40,250), outline=(255,111,159), width=8)
            d.text((85,80), f"AULAIA  •  {i+1:02d}/{total:02d}", font=small_font, fill=(255,111,159))
            heading=scene.get("heading",f"Cena {i+1}")
            y=140
            for line in wrap_words(heading, 38)[:2]:
                d.text((85,y),line,font=title_font,fill=(255,255,255)); y+=62
            d.line((85,y+5,W-100,y+5), fill=(255,79,145), width=3); y+=38
            visual=scene.get("visual","")
            for line in wrap_words("VISUAL: "+visual, 65)[:2]:
                d.text((85,y),line,font=small_font,fill=(170,190,220)); y+=29
            # summary subtitles/keywords in the scene card
            narration=scene.get("narration","")
            words=scene.get("keywords",[]) or []
            summary=" • ".join(words[:5]) if words else "Explicação passo a passo"
            d.rounded_rectangle((85, H-165, W-85, H-95), radius=18, fill=(35,43,64))
            d.text((110,H-145), summary[:72], font=body_font if len(summary)<40 else small_font, fill=(255,215,230))
            image_path=work/f"scene_{i:03d}.png"; img.save(image_path)
            clip=ImageClip(str(image_path)).with_duration(max(1,audio.duration)).with_audio(audio)
            clips.append(clip)
        final=concatenate_videoclips(clips, method="compose")
        final.write_videofile(str(out_mp4), fps=24, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None)
        final.close()
    finally:
        for c in clips:
            try: c.close()
            except: pass
        shutil.rmtree(work, ignore_errors=True)

if "script_data" not in st.session_state: st.session_state.script_data = None
if "pdf_text" not in st.session_state: st.session_state.pdf_text = ""

col1,col2=st.columns(2)
with col1:
    if st.button("2. Ler PDF e preparar roteiro", use_container_width=True, disabled=uploaded is None):
        with st.spinner("Lendo a apostila e organizando o conteúdo..."):
            try:
                pdftext=extract_pdf(uploaded)
                if len(pdftext.strip()) < 100: st.error("O PDF parece ser escaneado como imagem. Esta versão precisa de um PDF com texto selecionável.")
                else:
                    st.session_state.pdf_text=pdftext
                    st.session_state.script_data=make_script(pdftext,topic,duration,extra,api_key)
                    st.success(f"Roteiro preparado com {len(st.session_state.script_data['scenes'])} cenas.")
            except Exception as e: st.error(str(e))
with col2:
    if st.button("Limpar projeto", use_container_width=True):
        st.session_state.script_data=None; st.session_state.pdf_text=""; st.rerun()

if st.session_state.script_data:
    data=st.session_state.script_data
    st.subheader("3. Revise e edite as cenas")
    data["title"]=st.text_input("Título da videoaula",value=data.get("title","Videoaula AulaIA"))
    for idx, sc in enumerate(data["scenes"]):
        with st.expander(f"Cena {idx+1}: {sc.get('heading','Cena')} ", expanded=(idx==0)):
            sc["heading"]=st.text_input("Título da cena",sc.get("heading",""),key=f"h{idx}")
            sc["narration"]=st.text_area("Narração",sc.get("narration",""),height=130,key=f"n{idx}")
            sc["visual"]=st.text_input("Descrição visual",sc.get("visual",""),key=f"v{idx}")
            kw=st.text_input("Palavras-chave (separadas por vírgula)",", ".join(sc.get("keywords",[])),key=f"k{idx}")
            sc["keywords"]=[x.strip() for x in kw.split(",") if x.strip()]
    st.download_button("Baixar roteiro JSON",json.dumps(data,ensure_ascii=False,indent=2),file_name="roteiro_aulaia.json",mime="application/json")
    if st.button("4. Gerar videoaula MP4",use_container_width=True):
        if not st.session_state.pdf_text: st.error("Envie e processe um PDF primeiro.")
        else:
            progress=st.progress(0,text="Iniciando...")
            out=Path(tempfile.gettempdir())/"aulaia_videoaula.mp4"
            try:
                build_video(data,voice,style,out,progress)
                st.success("Videoaula criada!")
                st.video(str(out))
                st.download_button("⬇️ Baixar videoaula MP4",data=out.read_bytes(),file_name="videoaula_aulaia.mp4",mime="video/mp4")
            except Exception as e:
                st.error(f"Não foi possível renderizar o vídeo: {e}")
                st.caption("Confira se o serviço de voz está acessível e se o servidor possui memória suficiente.")

st.markdown("---")
st.caption("AulaIA é um protótipo. A geração de voz usa Edge TTS (serviço externo, gratuito no momento, sem garantia de disponibilidade/termos futuros). A geração de roteiro por IA usa a API Gemini se você informar uma chave; sem chave, o app organiza trechos extraídos do PDF, mas não reescreve o conteúdo como uma aula. Não envie documentos sensíveis.")
