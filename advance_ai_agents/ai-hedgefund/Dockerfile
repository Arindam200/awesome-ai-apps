# Use the official Motia base image
FROM motiadev/motia:latest


# Set working directory
WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies
RUN bun install

# Copy application source code
COPY . .

# Install Motia dependencies and build the project
RUN npx motia@latest install

# Expose the default Motia port
EXPOSE 3000

# Start the Motia application
CMD ["bun", "run", "dev"]