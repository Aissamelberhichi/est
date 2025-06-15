# Utiliser Node.js officiel
FROM node:20

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm install

COPY . .

# Construire l'application React pour production
RUN npm run build

# Utiliser un serveur léger pour servir l'application (par exemple serve)
RUN npm install -g serve

# Exposer le port 3000
EXPOSE 3000

# Lancer le serveur
CMD ["serve", "-s", "build", "-l", "3000"]
