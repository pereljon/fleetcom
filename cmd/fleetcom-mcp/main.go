// Command fleetcom-mcp runs the fleetcom MCP server over stdio.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pereljon/fleetcom/internal/mcpserver"
	"github.com/pereljon/fleetcom/internal/store"
)

func main() {
	dbPath := flag.String("db", store.DefaultDBPath(), "path to the fleetcom SQLite database")
	flag.Parse()

	s, err := store.Open(*dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "fleetcom-mcp: open %s: %v\n", *dbPath, err)
		os.Exit(1)
	}
	defer s.Close()

	if err := s.Migrate(); err != nil {
		fmt.Fprintf(os.Stderr, "fleetcom-mcp: migrate: %v\n", err)
		os.Exit(1)
	}

	server := mcpserver.NewServer(s)
	if err := server.Run(context.Background(), &mcp.StdioTransport{}); err != nil {
		fmt.Fprintf(os.Stderr, "fleetcom-mcp: %v\n", err)
		os.Exit(1)
	}
}
