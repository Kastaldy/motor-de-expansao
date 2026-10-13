# Releitura dos testes antigos com a medida de efeito (LEITURA, sem veredito)

Rodado em 2026-10-07 10:44. Método no topo de `releitura/01_releitura_efeito.py`, escrito antes de rodar.

## Por que reler

A régua antiga (cair ≥ 2 pontos no erro das 39 E no teste das 18) detecta um efeito real moderado em só 1–4% das vezes (simulação de 07/10). Então "não passou" quase não dizia nada sobre existir efeito. Aqui a pergunta é outra: **a variável tem efeito, e de que tamanho?**

## Como ler

- **Efeito:** quanto o faturamento (ou o balcão, ou o agregador) muda com a variável, com o resto do modelo igual. Masters e região: contra o DF/GO (master M1).
- **Faixa de 90%:** se cruza o zero, não dá para separar do acaso. **p:** chance de um efeito desse tamanho aparecer por acaso.
- **Correção:** com 8 variáveis por modelo, alguma "acerta" por acaso; "sobrevive à correção" desconta isso (Holm).
- **Aviso:** as 57 unidades já foram vistas e estes testes já rodaram. É leitura, não teste novo. Ter efeito também não é o mesmo que melhorar a previsão de unidade nova: o efeito pode existir e ser pequeno demais para mudar o erro.

| modelo | variável | teste anterior | n | efeito | faixa 90% | p | leitura |
|---|---|---|---|---|---|---|---|
| faturamento | masters (conjunto) | UNI-14/15: nenhum braço passou | 57 | M2 +16%; M3 +19%; outras +21% | — | 0.358 | não se distingue de zero |
| faturamento | região R1: fora do DF/GO | UNI-15 T1: não passou | 57 | +18% | +1% a +39% | 0.077 | efeito, mas não sobrevive à correção |
| faturamento | região R2: SP | UNI-15 T1: não passou | 57 | +21% | -1% a +48% | 0.127 | não se distingue de zero |
| faturamento | região R2: outras UFs | UNI-15 T1: não passou | 57 | +16% | -5% a +42% | 0.234 | não se distingue de zero |
| faturamento | tier do Wellhub do cadastro (unidade por nível de tier (ordinal)) | UNI-14 D: o mais perto, não passou | 56 | +21% | +7% a +36% | 0.009 | efeito claro (sobrevive à correção) |
| faturamento | estúdio × renda (por 1 desvio-padrão de renda, nas com estúdio) | UNI-14 C: não passou | 57 | -11% | -26% a +7% | 0.280 | não se distingue de zero |
| faturamento | mercado de agregador: parceiros por mil hab. (por +1 em log) | UNI-14 B: não passou | 57 | +12% | -52% a +159% | 0.831 | não se distingue de zero |
| faturamento | mercado de agregador: independentes (por +1 em log) | UNI-14 B: não passou | 57 | -9% | -54% a +79% | 0.810 | não se distingue de zero |
| balcão | masters (conjunto) | UNI-14/15: nenhum braço passou | 57 | M2 +1%; M3 -9%; outras -5% | — | 0.967 | não se distingue de zero |
| balcão | região R1: fora do DF/GO | UNI-15 T1: não passou | 57 | -3% | -19% a +16% | 0.774 | não se distingue de zero |
| balcão | região R2: SP | UNI-15 T1: não passou | 57 | -9% | -27% a +13% | 0.460 | não se distingue de zero |
| balcão | região R2: outras UFs | UNI-15 T1: não passou | 57 | +5% | -19% a +37% | 0.760 | não se distingue de zero |
| balcão | tier do Wellhub do cadastro (unidade por nível de tier (ordinal)) | UNI-14 D: o mais perto, não passou | 56 | +20% | +2% a +42% | 0.066 | efeito, mas não sobrevive à correção |
| balcão | estúdio × renda (por 1 desvio-padrão de renda, nas com estúdio) | UNI-14 C: não passou | 57 | -10% | -27% a +12% | 0.441 | não se distingue de zero |
| balcão | mercado de agregador: parceiros por mil hab. (por +1 em log) | UNI-14 B: não passou | 57 | -11% | -67% a +144% | 0.855 | não se distingue de zero |
| balcão | mercado de agregador: independentes (por +1 em log) | UNI-14 B: não passou | 57 | +2% | -54% a +126% | 0.968 | não se distingue de zero |
| agregador | masters (conjunto) | UNI-14/15: nenhum braço passou | 56 | M2 +91%; M3 +166%; outras +131% | — | 0.000 | efeito claro (sobrevive à correção) |
| agregador | região R1: fora do DF/GO | UNI-15 T1: não passou | 56 | +114% | +68% a +172% | 0.000 | efeito claro (sobrevive à correção) |
| agregador | região R2: SP | UNI-15 T1: não passou | 56 | +166% | +101% a +251% | 0.000 | efeito claro (sobrevive à correção) |
| agregador | região R2: outras UFs | UNI-15 T1: não passou | 56 | +61% | +23% a +111% | 0.003 | efeito claro (sobrevive à correção) |
| agregador | tier do Wellhub do cadastro (unidade por nível de tier (ordinal)) | UNI-14 D: o mais perto, não passou | 56 | +18% | -2% a +42% | 0.143 | não se distingue de zero |
| agregador | estúdio × renda (por 1 desvio-padrão de renda, nas com estúdio) | UNI-14 C: não passou | 56 | -2% | -23% a +25% | 0.895 | não se distingue de zero |
| agregador | mercado de agregador: parceiros por mil hab. (por +1 em log) | UNI-14 B: não passou | 56 | +112% | -40% a +655% | 0.329 | não se distingue de zero |
| agregador | mercado de agregador: independentes (por +1 em log) | UNI-14 B: não passou | 56 | -42% | -80% a +74% | 0.417 | não se distingue de zero |

Masters (conjunto): teste das 3 dummies juntas (M2, M3, outras contra M1 = DF/GO); o efeito de cada uma vem ao lado, sem faixa.

