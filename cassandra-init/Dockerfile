FROM cassandra:4.1

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl

# Copy initialization script
COPY cassandra-init/init.sh /init.sh

# Make script executable
RUN chmod +x /init.sh

# Set the entrypoint to our init script
ENTRYPOINT ["/init.sh"]
