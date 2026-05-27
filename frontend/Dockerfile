FROM node:18-alpine

WORKDIR /app

EXPOSE 3000

# npm install runs at container startup so node_modules land in the
# named volume (frontend_node_modules), which outlives bind-mount resets
CMD ["sh", "-c", "npm install && npm run dev"]
