# Fábrica de Canais — modelo

Motor gratuito para criar e manter canais "dark" (sem rosto) de Shorts no YouTube, com roteiro conferido,
imagens, narração, animação e entrega no seu Telegram. Tudo roda na **sua** conta do GitHub, com as **suas**
chaves gratuitas. Ninguém além de você vê suas chaves, seus canais ou seus vídeos.

Use pela página: **https://fabrica-de-canais.github.io/** (botão *Começar*). Passo a passo completo: [MANUAL.md](MANUAL.md).

## Como começar (uns 20 minutos, uma vez só)
1. Clique em **Use this template → Create a new repository**. Deixe **Private**.
2. Na página da Fábrica, cole um token do GitHub com acesso só a esse repositório
   (Actions, Contents e Secrets em *Read and write*).
3. Cadastre as chaves pela página (ela explica onde pegar cada uma):
   - `GEMINI_API_KEY` — roteiros (Google AI Studio, gratuito);
   - `GOOGLE_TTS_KEY` — narração (Google Cloud Text-to-Speech; pede cartão cadastrado, o uso fica no nível gratuito);
   - `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID` — imagens (Cloudflare Workers AI, 10 mil "neurônios" grátis por dia).
4. Em **+ Novo canal**, escreva a ideia. Os agentes montam o canal, a marca e um Short de teste.
5. Na aba **Lançamento** do canal, ligue o bot do Telegram, crie o canal no YouTube e ative a produção diária.

## O que roda onde
| peça | onde |
|---|---|
| Rotina diária (21h17, Brasília) | GitHub Actions do seu repositório |
| Roteiro e conferência de fatos (3 passadas) | Gemini, nível gratuito |
| Imagens | Cloudflare Workers AI (FLUX.2 klein), nível gratuito |
| Narração | Google Cloud Text-to-Speech |
| Entrega do vídeo, título, descrição e tags | seu bot do Telegram |

A cota gratuita de imagens dá para cerca de **2 Shorts por dia** por conta Cloudflare. Para mais canais,
use outra conta Cloudflare e preencha `"cloudflare": "2"` no `canal.json` (segredos `CLOUDFLARE_API_TOKEN_2`
e `CLOUDFLARE_ACCOUNT_ID_2`).

## Responsabilidade
Você publica os vídeos e responde pelo seu canal. Revise cada Short antes de postar, declare o uso de IA
quando o YouTube pedir e siga as regras do Programa de Parcerias (o YouTube não monetiza conteúdo
inautêntico, repetitivo ou reutilizado). O projeto é oferecido como está, sem garantia e sem suporte.

Licença MIT.
