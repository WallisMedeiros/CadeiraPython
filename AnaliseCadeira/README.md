# Análise Estrutural de Cadeira — Projeto A3 (Resistência dos Materiais)

Software em **Python** que modela uma cadeira como um conjunto de vigas e apoios,
calcula reações vinculares, diagramas de esforços internos (N, V, M), tensões normais
(esforço axial + momento fletor) e deformações, e informa se a cadeira é
**segura ou não**. Gera um **relatório PDF** que é ao mesmo tempo a parte escrita do
projeto e o memorial de cálculo completo (ver "Relatório PDF" abaixo).

Roda de duas formas, com **o mesmo núcleo de cálculo em Python** (`nucleo/`):

- **Site** (Flask): `app.py` + pasta `static/`
- **Desktop** (PyQt5): `main.py` + pasta `interface/`

## Rodar o site no seu computador

1. Instale o Python 3.10 ou mais novo (no Windows, marque *"Add Python to PATH"*).
2. Dê dois cliques em `executar_windows.bat` (Windows) ou rode `./executar_linux_mac.sh`.
   Manualmente:
   ```
   pip install -r requirements.txt
   python app.py
   ```
3. Abra **http://localhost:5000** no navegador.

## Colocar o site no ar (link público, grátis)

### Opção 1 — Render.com (recomendado)

1. Crie um repositório no GitHub e envie esta pasta inteira para ele.
2. Em [render.com](https://render.com), faça login com o GitHub e clique em
   **New → Blueprint**. Escolha o repositório: o arquivo `render.yaml` já configura tudo.
   (Ou **New → Web Service** com *Build* `pip install -r requirements.txt` e
   *Start* `gunicorn app:app --bind 0.0.0.0:$PORT`.)
3. Em 3–5 minutos o site fica disponível em `https://analise-cadeira.onrender.com`
   (o nome final aparece no painel do Render).

No plano gratuito o servidor "dorme" após 15 min sem acesso; a primeira visita depois
disso demora cerca de 50 s para abrir. Para uma apresentação, abra o link alguns
minutos antes.

### Opção 2 — Railway, Fly.io, PythonAnywhere

Qualquer serviço que rode Python serve. O comando de início está no `Procfile`:
`gunicorn app:app`.

## Rodar a versão desktop

```
pip install -r requirements-desktop.txt
python main.py
```

## Testes

```
python testes/test_calculos.py
```

## API (usada pelo site)

| Rota | Método | O que faz |
|---|---|---|
| `/api/opcoes` | GET | materiais, tipos de seção e valores padrão |
| `/api/analisar` | POST | recebe as entradas (JSON) e devolve resultados, diagramas e memorial |
| `/api/relatorio` | POST | `{entradas, integrantes, turma}` → arquivo PDF |

Os nomes dos campos do JSON são os mesmos da classe `Entradas` em `nucleo/calculos.py`
(`massa_kg`, `altura_mm`, `largura_mm`, `material`, `tipo_secao`, `espessura_perna_mm`,
`dimensao_travessa_mm`…).

## Entradas

| Entrada | Observação |
|---|---|
| Peso da pessoa (kg) | |
| Altura da cadeira | altura do assento ao piso = comprimento das pernas |
| Largura do assento | |
| Espessura das pernas | dimensão externa da seção (a, d, D ou B); nas vazadas também a interna (d ou b) |
| Material | Madeira de eucalipto (classe C40), Aço SAE 1020 (laminado a quente) ou Alumínio 6061-T6 |
| Profundidade do assento ℓ | vão da travessa lateral |
| FS | fator de segurança (σ_adm = σ_lim / FS) |

Premissas fixas (não editáveis): carga estática P = m·g (g = 10 m/s², sem fator dinâmico),
sem força horizontal/atrito e excentricidade e = 0 mm (constante `EXCENTRICIDADE_MM` em
`nucleo/calculos.py`).

## Materiais

| Material | Condição adotada | σ_lim usada | E | Fonte |
|---|---|---|---|---|
| Madeira - Eucalipto (C40) | eucalipto classificado na classe C40 das dicotiledôneas, U = 12 % | f_c0,k = 40 MPa | 19,5 GPa | ABNT NBR 7190:1997 |
| Aço SAE 1020 | laminado a quente | σ_e = 210 MPa (σ_r = 380 MPa) | 200 GPa | SAE/ASM Handbook vol. 1 |
| Alumínio 6061-T6 | têmpera T6 | σ_e = 276 MPa (σ_r = 310 MPa) | 68,9 GPa | ASM / Aluminum Association |

## Saídas

- **Tensão máxima nas pernas** (σ = N/A + M/W, com M = 0 → compressão simples) e na travessa do assento (σ = M/W)
- Indicação **CADEIRA SEGURA / NÃO SEGURA**, motivo da falha e taxa de uso de cada verificação
- Reações, diagramas N/V/M da perna e V/M/linha elástica da travessa
- Distribuição da tensão normal nas seções críticas (perna e travessa)
- Deformações (encurtamento da perna, flecha da travessa) e massa máxima admissível
- Memorial de cálculo passo a passo (o que/por quê → fórmula → substituição → resultado →
  interpretação) e PDF

## Seções transversais disponíveis

Quatro, para pernas e travessas (os campos se adaptam à seção):

| Seção | Entrada | A | I | W |
|---|---|---|---|---|
| Quadrada maciça | lado a | a² | a⁴/12 | a³/6 |
| Circular maciça | diâmetro d | π·d²/4 | π·d⁴/64 | π·d³/32 |
| Circular vazada | D externo, d interno | π(D² − d²)/4 | π(D⁴ − d⁴)/64 | π(D⁴ − d⁴)/(32·D) |
| Quadrada vazada | B externo, b interno | B² − b² | (B⁴ − b⁴)/12 | (B⁴ − b⁴)/(6·B) |

A dimensão interna deve ser maior que zero e menor que a externa.

## Relatório PDF

Capa (integrantes, professores, turma) · Sumário · 1 Introdução · 2 Objetivos ·
3 Fundamentação teórica · 4 Metodologia (etapas, tecnologias, implementação, materiais e
seções disponíveis × selecionados, parâmetros de entrada, modelagem) · 5 Memorial de cálculo
(dados, geometria, carregamento, reações, esforços, diagramas, tensões, deformações,
verificação) · 6 Resultados e discussão (resultados, interpretação dos gráficos, discussão,
limitações) · 7 Conclusão · Referências.

Os nomes dos professores da capa ficam em `PROFESSORES`, no início de `nucleo/relatorio.py`.

## Estrutura do código

```
app.py                  servidor web (Flask): expõe o núcleo por HTTP
static/                 interface do site (HTML, CSS, JavaScript com gráficos em SVG)
main.py                 inicia a versão desktop
interface/janela.py     janela PyQt5
nucleo/materiais.py     banco de materiais
nucleo/secoes.py        A, I, c, W das 4 seções (maciças e vazadas)
nucleo/calculos.py      modelo estrutural, cálculos e memorial
nucleo/diagramas.py     gráficos (Matplotlib) usados no PDF e no desktop
nucleo/relatorio.py     relatório PDF (ReportLab)
testes/                 testes comparando com cálculo manual
render.yaml, Procfile   configuração de hospedagem
```

## Hipóteses do modelo

Carga estática e vertical P = m·g, centrada (e = 0), sem força horizontal. 4 pernas
iguais, cada uma com R = P/4 em compressão simples (V = M = 0); travessas laterais
bi-apoiadas com carga concentrada Q = P/2 no meio do vão (M = Q·ℓ/4, δ = Q·ℓ³/48EI);
material elástico-linear; peso próprio desprezado. Critério: σ ≤ σ_lim/FS nas pernas e
na travessa.
