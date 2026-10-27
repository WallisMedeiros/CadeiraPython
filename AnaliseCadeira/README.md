# Análise Estrutural de Cadeira — Projeto A3 (Resistência dos Materiais)

Software em **Python** que modela uma cadeira como um conjunto de vigas e apoios,
calcula reações vinculares, diagramas de esforços internos (N, V, M), tensões normais
(esforço axial + momento fletor), deformações e flambagem, e informa se a cadeira é
**segura ou não**. Gera um **relatório PDF** com Integrantes, Introdução, Objetivos,
Metodologia, Resultados (memorial de cálculo + diagramas) e Conclusão.

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
(`massa_kg`, `altura_mm`, `largura_mm`, `material`, `tipo_secao`, `espessura_perna_mm`…).

## Entradas

| Entrada | Observação |
|---|---|
| Peso da pessoa (kg) | |
| Altura da cadeira | altura do assento ao piso = comprimento das pernas |
| Largura do assento | |
| Espessura das pernas | lado ou diâmetro; seções maciças ou tubulares |
| Material | Madeira (Pinus C25, Eucalipto C40), Aço (SAE 1020, A36), Alumínio (6061-T6, 6063-T5) ou personalizado |
| Profundidade do assento | vão da travessa lateral |
| Fator dinâmico φ | impacto ao sentar (padrão 1,5) |
| Coef. horizontal μ | força horizontal F_H = μ·W (padrão 0,10) |
| Excentricidade e | carga deslocada para a frente |
| FS e K | fator de segurança e coeficiente de flambagem |

## Saídas

- **Tensão máxima nas pernas** (σ = N/A + M/W) e na travessa do assento (σ = M/W)
- Indicação **CADEIRA SEGURA / NÃO SEGURA**, motivo da falha e taxa de uso de cada verificação
- Reações, diagramas N/V/M da perna e V/M/linha elástica da travessa
- Deformações, flambagem (Euler), tombamento e massa máxima admissível
- Memorial de cálculo passo a passo (fórmula → substituição → resultado) e PDF

## Estrutura do código

```
app.py                  servidor web (Flask): expõe o núcleo por HTTP
static/                 interface do site (HTML, CSS, JavaScript com gráficos em SVG)
main.py                 inicia a versão desktop
interface/janela.py     janela PyQt5
nucleo/materiais.py     banco de materiais
nucleo/secoes.py        A, I, W, r das seções
nucleo/calculos.py      modelo estrutural, cálculos e memorial
nucleo/diagramas.py     gráficos (Matplotlib) usados no PDF e no desktop
nucleo/relatorio.py     relatório PDF (ReportLab)
testes/                 testes comparando com cálculo manual
render.yaml, Procfile   configuração de hospedagem
```

## Hipóteses do modelo

4 pernas iguais engastadas no quadro do assento e livres no piso (flexo-compressão);
travessas laterais bi-apoiadas com carga concentrada Q = W/2 (conservador); material
elástico-linear; peso próprio desprezado. Critério: σ_máx ≤ σ_lim/FS, P_cr/N ≥ FS e
reação traseira ≥ 0 (sem tombamento).
