# Manual da Fábrica de Canais

A Fábrica de Canais cria e mantém canais de Shorts sem rosto no YouTube, de graça, rodando inteira na sua conta do GitHub com as suas chaves. Você dá uma ideia, quatro agentes de IA montam o canal e, depois de ligado, todo dia chega no seu Telegram um Short pronto para postar, com título, descrição e tags.

Página: **https://fabrica-de-canais.github.io/**

```
UMA VEZ POR CANAL (pela página)
  Sua ideia → 4 agentes montam → Marca + Short teste → Lançamento
                                                          │ ativar produção
TODO DIA ÀS 21h17 (sozinho)                               ▼
  Roteiro conferido → Imagens e narração → Vídeo montado → Chega no Telegram → Você revisa e posta
```

| Peça | Onde roda | Custo |
| --- | --- | --- |
| Página da Fábrica | seu navegador (não guarda nada em servidor) | grátis |
| Rotina diária e esteira de criação | GitHub Actions do seu repositório privado | grátis |
| Roteiro e conferência de fatos (3 passadas) | Gemini, nível gratuito | grátis |
| Imagens | Cloudflare Workers AI (FLUX.2 klein) | grátis até 10 mil neurônios por dia |
| Narração | Google Cloud Text-to-Speech | nível gratuito (pede cartão cadastrado) |
| Entrega do vídeo | seu bot do Telegram | grátis |

A Fábrica não publica no YouTube por você: cada Short chega no Telegram e você revisa e posta.

## 1. Antes de começar

A configuração leva uns 20 minutos e é feita uma vez só. Tenha à mão:

- **Conta no GitHub** (gratuita). É onde fica o seu repositório privado e onde a rotina roda.
- **Conta Google** para o Gemini e para o Google Cloud. O Text-to-Speech só é ativado com um cartão cadastrado; o uso de um canal fica dentro do nível gratuito.
- **Conta na Cloudflare** (gratuita), para as imagens.
- **Telegram** no celular, para receber os Shorts.
- **Uma conta Google para o YouTube** onde você vai criar o canal. O YouTube pede verificação por SMS na primeira vez que você cria um segundo canal na mesma conta.

Use um computador para a configuração. Depois disso, o dia a dia pode ser todo pelo celular.

## 2. Instalação

Abra https://fabrica-de-canais.github.io/. A tela **Começar** guia os três passos:

1. **Copie o modelo.** Clique em **Abrir o modelo no GitHub** → **Use this template** → **Create a new repository**. Dê um nome (ex.: `minha-fabrica`), marque **Private** e confirme.
2. **Crie um token do GitHub.** Clique em **Criar o token**: o GitHub abre com nome e permissões preenchidos (Actions, Contents e Secrets em Read and write).
   - Em **Repository access**, escolha **Only select repositories** e marque o repositório que você acabou de criar.
   - Clique em **Generate token** e copie na hora: o GitHub mostra o token uma vez só.
3. **Conecte.** Na Fábrica, preencha **Seu repositório** (`seu-usuario/minha-fabrica`) e **Token**, e clique em **Conectar**.

O token fica guardado só no navegador em que você conectou. Em outro aparelho, conecte de novo. Perdeu o token? Em github.com/settings/personal-access-tokens, abra **Fabrica de Canais** e clique em **Regenerate token**.

## 3. Cadastrar as chaves

Na Fábrica, abra **Chaves**. Cole cada chave no seu campo e clique em **Salvar**; ela vai criptografada direto para os segredos do seu repositório e o selo muda para **cadastrada**. Salve uma de cada vez.

| Chave | Para que serve | Onde pegar |
| --- | --- | --- |
| Gemini | roteiros e conferência | https://aistudio.google.com/apikey → **Create API key** |
| Google Text-to-Speech | narração | https://console.cloud.google.com/apis/credentials : crie um projeto, ative a API **Cloud Text-to-Speech** e, em **Credenciais**, crie uma **chave de API** |
| Cloudflare Workers AI | imagens | https://dash.cloudflare.com/profile/api-tokens → **Create Token** → modelo **Workers AI** |
| ID da conta Cloudflare | imagens | painel da Cloudflare → **Workers AI**: o **Account ID** aparece na lateral (32 letras e números) |

O GitHub nunca mostra o valor de um segredo de volta, só o nome. Para trocar uma chave, cole a nova no mesmo campo e salve.

## 4. Criar um canal

Em **+ Novo canal**, escreva a ideia e clique em **Montar canal**. A esteira leva de 8 a 12 minutos e usa cerca de 40% da cota diária de imagens.

- **Ideia do canal:** o assunto e, se quiser, para quem. Ex.: "curiosidades de animais que quase ninguém conhece, para adultos".
- **Estilo visual** (opcional): massinha, Funko, aquarela, pixel art...
- **Voz:** masculina ou feminina.
- **Identificador:** vira a pasta do canal. Letras minúsculas e hífens.

A esteira mostra cada etapa:

1. **Agentes montam o canal.** O estrategista avalia o nicho (nota de 0 a 10, veredito, riscos de monetização, RPM estimado). O roteirista desenha as cenas fixas do Short e sugere 30 temas. O diretor de arte define o estilo das imagens e as cores. O operador escreve a descrição e as palavras-chave do YouTube.
2. **Foto de perfil e capa.** Duas fotos de perfil e uma capa 2560×1440 com o nome dentro da área que aparece no celular.
3. **Short de teste.** Um Short completo com o primeiro tema da fila, sem tirar o tema da fila.

| Aba | O que tem | O que dá para fazer |
| --- | --- | --- |
| Ficha | veredito, formato, concorrência, riscos, ideias de vídeo longo | ler antes de decidir |
| Prévia | o Short de teste e o que a conferência cortou | **Refazer o teste** |
| Marca | fotos de perfil e capa | abrir em tamanho real e salvar; **Gerar outra marca** |
| Fila | os temas, um por linha | editar e **Salvar fila**; **Pedir mais 30 temas à IA** |
| Lançamento | o passo a passo para colocar no ar | ligar o Telegram, copiar os textos |

Se a nota do estrategista for baixa, vale mais tentar outra ideia do que insistir.

## 5. Lançar o canal

Tudo fica na aba **Lançamento**, na ordem certa. Um canal só produz depois do último passo.

1. **Bot do Telegram.** Fale com **@BotFather**, mande `/newbot`, escolha um nome e copie o token. Mande qualquer mensagem para o bot novo. Cole o token na Fábrica e clique em **Ligar o Telegram**: ela descobre a sua conversa sozinha, guarda tudo criptografado e manda uma mensagem de teste.
2. **Canal no YouTube.** Em youtube.com/channel_switcher → **Crie um canal**, use o nome e o @ sugeridos.
3. **Foto e capa.** Em **YouTube Studio → Personalização → Branding**, suba a foto e a capa da aba **Marca**.
4. **Textos.** Cole a descrição em **Personalização → Informações básicas**. Em **Configurações → Canal**, cole as palavras-chave, escolha o país e marque "não é conteúdo para crianças". Em **Padrões de envio**, cole o rodapé e escolha a categoria.
5. **Ativar.** No topo do canal, clique em **Ativar produção diária**. O primeiro Short sai às 21h17.

## 6. O dia a dia

Todo dia às 21h17 (Brasília), logo depois que a cota de imagens renova, cada canal ativo produz um Short. Se o GitHub atrasar, a rotina tenta de novo às 22h37 e às 23h47; cada canal produz uma vez só por dia.

No Telegram chegam o vídeo vertical (35 a 55 s), a mensagem com título, descrição e tags e, se houver, a lista do que a conferência cortou.

- **Para postar:** baixe o vídeo, assista inteiro, abra o YouTube Studio no canal certo, **Criar → Enviar vídeos**, cole título, descrição e tags, responda a pergunta sobre IA e publique.
- **Fila de temas:** a primeira linha da aba **Fila** é o próximo Short. Edite e clique em **Salvar fila**. Quando acabar, use **Pedir mais 30 temas à IA**.
- **Pausar:** o botão **Pausar** no topo do canal para a produção sem apagar nada.
- Se algo falhar, chega um aviso no Telegram e o tema volta para a fila.

## 7. Limites e cotas

Uma conta Cloudflare gratuita dá para cerca de 2 Shorts por dia. Números aproximados:

| Recurso | Limite gratuito | Quanto a Fábrica usa |
| --- | --- | --- |
| Imagens (Cloudflare) | 10 mil neurônios por dia, renova às 21h (Brasília) | cerca de 40% por Short ou por canal novo |
| GitHub Actions (repositório privado) | 2.000 minutos por mês | cerca de 7 minutos por Short |
| Gemini | cota diária do nível gratuito | 4 a 6 chamadas por Short |
| Text-to-Speech | nível gratuito mensal do Google | cerca de 600 caracteres por Short |

**Mais de 2 canais:** crie outra conta Cloudflare, cadastre `CLOUDFLARE_API_TOKEN_2` e `CLOUDFLARE_ACCOUNT_ID_2` em Settings → Secrets and variables → Actions e, no `canal.json` do canal, ponha `"cloudflare": "2"`.

## 8. Boas práticas e regras do YouTube

Você publica e responde pelo seu canal.

- **Assista antes de postar.** A conferência corta o que não tem certeza, mas IA ainda erra.
- **Declare o uso de IA** quando as imagens parecerem cenas reais. Na dúvida, marque **Sim**.
- **Fuja do conteúdo inautêntico.** O YouTube não monetiza conteúdo repetitivo, reutilizado ou produzido em massa sem valor próprio. Varie os temas e evite canais iguais.
- **Nada de pessoas reais, marcas ou obras protegidas** nos temas.
- **Monetização:** 1.000 inscritos e 10 milhões de visualizações de Shorts em 90 dias, ou 1.000 inscritos e 4.000 horas de vídeos longos em 12 meses. Confira a [página oficial](https://support.google.com/youtube/answer/72851), os requisitos mudam.
- **Responda comentários** e use as respostas para montar a fila.

## 9. Problemas comuns

| O que aparece | Causa provável | Como resolver |
| --- | --- | --- |
| "O token não foi aceito" | token errado, apagado ou sem acesso | gere outro e confira **Only select repositories** |
| "Repositório não encontrado" | nome diferente do GitHub | use exatamente `usuario/repositorio` |
| Aviso: cota de imagens acabou | testes ou muitos canais no dia | espere as 21h; use uma segunda conta Cloudflare |
| Esteira sem marca ou sem prévia | cota de imagens esgotada | depois das 21h30, **Gerar outra marca** e **Refazer o teste** |
| "A esteira parou" | chave faltando ou errada | **Ver no GitHub**, leia a etapa em vermelho, confira as chaves |
| "Mande uma mensagem para o bot" | o bot não recebeu mensagem | mande "oi" ao bot e clique de novo |
| Nenhum Short às 21h17 | o GitHub atrasou | espere 22h37 e 23h47 |
| Short não sai nunca | canal pausado ou Telegram pendente | confira **Produzindo** e o Telegram em **Lançamento** |
| "A fila de temas está vazia" | todos os temas viraram Short | **Pedir mais 30 temas à IA** |

Projeto aberto (MIT), oferecido como está, sem garantia e sem suporte.
