import base64
import re
import urllib.request
from pathlib import Path

p = Path("index.html")
s = p.read_text(encoding="utf-8")
m = re.search(r'atob\("([A-Za-z0-9+/=]+)"\)', s)
if not m:
    raise SystemExit("JS embutido não encontrado.")
js = base64.b64decode(m.group(1)).decode("utf-8")

pairs = [
    ("const canOwnConfig=await rz7Permission('provas.configurar_proprias');",
     "const canOwnConfig=await rz7Permission('provas.configurar_sistema');"),
    ("const canOther=await rz7Permission('provas.configurar_outras');",
     "const canOther=await rz7Permission('provas.configurar_sistema');"),
    ("const canOwnQuestions=await rz7Permission('provas.editar_questoes_proprias');\n const canOtherQuestions=await rz7Permission('provas.editar_questoes_outras');",
     "const canOwnQuestions=await rz7Permission('provas.configurar_sistema');\n const canOtherQuestions=await rz7Permission('provas.configurar_sistema');"),
    ("const canEdit=perms.includes('provas.editar_questoes_outras')||proof.criado_por===profile?.instrutor?.id&&perms.includes('provas.editar_questoes_proprias');",
     "const canEdit=perms.includes('provas.configurar_sistema');"),
    ("Cargo ${escapeHtml(auth.profile.nivel||'instrutor')}",
     "Cargo ${escapeHtml(auth.profile?.cargo?.nome||auth.profile?.nivel||'instrutor')}"),
    ("Cargo atual: <strong>${escapeHtml(auth.profile.nivel||'instrutor')}</strong>",
     "Cargo atual: <strong>${escapeHtml(auth.profile?.cargo?.nome||auth.profile?.nivel||'instrutor')}</strong>")
]
for old, new in pairs:
    js = js.replace(old, new)

if "async function loadRz7Identity()" not in js:
    helper = """async function loadRz7Identity(){
 try{
  const {data,error}=await ensureSupabase().rpc('obter_configuracao_rz7',{p_chave:'identidade'});
  if(error) throw error;
  const v=data||{};
  const url=typeof v.logo_url==='string'?v.logo_url:'';
  const alt=typeof v.logo_alt==='string'&&v.logo_alt?v.logo_alt:'La Hermandad RZ7';
  document.querySelectorAll('.brand-logo,.hero-logo').forEach(img=>{if(url){img.src=url;img.alt=alt;img.style.display='';}});
  document.querySelectorAll('.brand-logo-fallback,.hero-logo-fallback').forEach(el=>{if(url)el.style.display='none';});
  return v;
 }catch(e){return {};}
}
"""
    marker = "async function renderAdminPanel(){"
    if marker not in js:
        raise SystemExit("Painel administrativo não encontrado.")
    js = js.replace(marker, helper + marker, 1)

if "['identity','🎨 Identidade']" not in js:
    marker = "['roles','⚙️ Cargos & permissões']"
    if marker not in js:
        raise SystemExit("Abas administrativas não encontradas.")
    js = js.replace(marker, marker + ",['identity','🎨 Identidade']", 1)

if "const renderIdentity=async()=>{" not in js:
    panel = """  const renderIdentity=async()=>{
   const current=await loadRz7Identity();
   setPanel('identity',`<div class="card"><div class="card-title">🎨 IDENTIDADE DO SISTEMA RZ7</div><div class="card-text">Área exclusiva para alterar a logo exibida no sistema.</div><div class="form-grid" style="margin-top:14px"><label class="form-field"><span>URL da logo</span><input id="rz7LogoUrl" class="form-input" value="${escapeHtml(current.logo_url||'')}" placeholder="https://.../logo.png"></label><label class="form-field"><span>Texto alternativo</span><input id="rz7LogoAlt" class="form-input" value="${escapeHtml(current.logo_alt||'La Hermandad RZ7')}"></label></div><div class="button-group" style="margin-top:14px"><button class="button" id="saveRz7Logo" type="button">💾 SALVAR LOGO</button><button class="button secondary" id="resetRz7Logo" type="button">↩ RESTAURAR LOGO PADRÃO</button></div><div id="rz7LogoMsg" class="card-text" style="margin-top:10px"></div></div>`);
   const save=$('saveRz7Logo'),reset=$('resetRz7Logo'),msg=$('rz7LogoMsg');
   save.addEventListener('click',async()=>{try{save.disabled=true;const url=$('rz7LogoUrl').value.trim(),alt=$('rz7LogoAlt').value.trim()||'La Hermandad RZ7';const {error}=await ensureSupabase().rpc('salvar_configuracao_rz7',{p_chave:'identidade',p_valor:{logo_url:url,logo_alt:alt}});if(error)throw error;await loadRz7Identity();msg.textContent='Logo atualizada com sucesso.';}catch(e){msg.textContent='Não foi possível salvar: '+(e.message||e);}finally{save.disabled=false;}});
   reset.addEventListener('click',async()=>{try{reset.disabled=true;const {error}=await ensureSupabase().rpc('salvar_configuracao_rz7',{p_chave:'identidade',p_valor:{logo_url:'',logo_alt:'La Hermandad RZ7'}});if(error)throw error;$('rz7LogoUrl').value='';$('rz7LogoAlt').value='La Hermandad RZ7';await loadRz7Identity();msg.textContent='Logo padrão restaurada.';}catch(e){msg.textContent='Não foi possível restaurar: '+(e.message||e);}finally{reset.disabled=false;}});
  };
"""
    marker = "  function activateTab(id){"
    if marker not in js:
        raise SystemExit("Roteador administrativo não encontrado.")
    js = js.replace(marker, panel + marker, 1)

js = js.replace("else if(id==='roles')renderRoles();",
                "else if(id==='roles')renderRoles();else if(id==='identity')renderIdentity();")

if "setConfig(c);\n await loadRz7Identity();\n await syncOpenProofFromDb();" not in js:
    js = js.replace("setConfig(c);\n await syncOpenProofFromDb();",
                    "setConfig(c);\n await loadRz7Identity();\n await syncOpenProofFromDb();", 1)

enc = base64.b64encode(js.encode("utf-8")).decode("ascii")
s = s[:m.start(1)] + enc + s[m.end(1):]

pat = re.compile(r'<script[^>]+src=["\']https://(?:cdn\.jsdelivr\.net|unpkg\.com)/[^"\']*supabase-js@2[^"\']*["\'][^>]*></script>', re.I)
if pat.search(s):
    lib = urllib.request.urlopen(
        "https://unpkg.com/@supabase/supabase-js@2.117.0/dist/umd/supabase.min.js",
        timeout=30
    ).read().decode("utf-8")
    s = pat.sub("<script>\n/* Supabase JS inline RZ7 */\n" + lib + "\n</script>", s, count=1)

p.write_text(s, encoding="utf-8")
print("RZ7 index atualizado.")
