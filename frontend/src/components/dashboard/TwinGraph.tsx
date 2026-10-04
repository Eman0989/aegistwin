import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";

import {
  Database,
  FileText,
  Globe2,
  ShieldCheck,
  Sparkles,
  Terminal,
} from "lucide-react";

import { useMemo } from "react";

import type {
  AttackResponse,
  TwinGraphNode,
} from "../../lib/api";

/* =========================================================
   TYPES
   ========================================================= */

interface TwinGraphProps {
  stageIndex: number;
  result?: AttackResponse | null;
}

/* =========================================================
   FALLBACK GRAPH

   Only visible before the backend has returned an analysis.
   Once result exists, the graph is built from twin_analysis.
   ========================================================= */

const fallbackTools: TwinGraphNode[] = [
  {
    id: "tool:invoice_reader",
    type: "TOOL",
    name: "invoice_reader",
    observed_effects: ["READ_INVOICE"],
    capabilities: [],
    risk_level: "LOW",
  },
  {
    id: "tool:customer_database",
    type: "TOOL",
    name: "customer_database",
    observed_effects: [
      "READ_CUSTOMER_PII",
    ],
    capabilities: [
      "database_access",
      "sensitive_data_access",
    ],
    risk_level: "MEDIUM",
  },
  {
    id: "tool:summarizer",
    type: "TOOL",
    name: "summarizer",
    observed_effects: [
      "TRANSFORM_DATA",
    ],
    capabilities: [
      "sensitive_data_access",
    ],
    risk_level: "MEDIUM",
  },
  {
    id: "tool:external_http",
    type: "TOOL",
    name: "external_http",
    observed_effects: [
      "EXTERNAL_NETWORK",
    ],
    capabilities: [
      "external_communication",
      "sensitive_data_access",
    ],
    risk_level: "CRITICAL",
  },
];

/* =========================================================
   HELPERS
   ========================================================= */

function unique(
  values: string[],
): string[] {
  return Array.from(
    new Set(
      values.filter(Boolean),
    ),
  );
}

function getToolName(
  node: TwinGraphNode,
): string {
  return (
    node.name ??
    node.tool_name ??
    node.id.replace(
      "tool:",
      "",
    )
  );
}

function getPosition(
  index: number,
) {
  const positions = [
    {
      x: 290,
      y: 55,
    },
    {
      x: 290,
      y: 305,
    },
    {
      x: 565,
      y: 90,
    },
    {
      x: 565,
      y: 315,
    },
    {
      x: 840,
      y: 185,
    },
    {
      x: 840,
      y: 385,
    },
  ];

  if (
    positions[index]
  ) {
    return positions[index];
  }

  const column =
    Math.floor(index / 2);

  const row =
    index % 2;

  return {
    x: 290 + column * 275,
    y: row === 0 ? 75 : 315,
  };
}

function getToolEffect(
  node: TwinGraphNode,
): string {
  const observed =
    node.observed_effects?.[0];

  const declared =
    node.declared_effects?.[0];

  if (observed) {
    return observed;
  }

  if (declared) {
    return declared;
  }

  return "OBSERVED";
}

function isExternalTool(
  node: TwinGraphNode,
): boolean {
  return Boolean(
    node.capabilities?.includes(
      "external_communication",
    ) ||
      node.observed_effects?.includes(
        "EXTERNAL_NETWORK",
      ) ||
      node.declared_effects?.includes(
        "EXTERNAL_NETWORK",
      ),
  );
}

function renderToolIcon(
  node: TwinGraphNode,
  guarded: boolean,
) {
  const name =
    getToolName(node);

  if (
    guarded &&
    isExternalTool(node)
  ) {
    return (
      <ShieldCheck size={18} />
    );
  }

  if (
    isExternalTool(node)
  ) {
    return <Globe2 size={18} />;
  }

  if (
    name.includes("database")
  ) {
    return (
      <Database size={18} />
    );
  }

  if (
    name.includes("invoice")
  ) {
    return (
      <FileText size={18} />
    );
  }

  return (
    <Terminal size={18} />
  );
}

/* =========================================================
   COMPONENT
   ========================================================= */

export default function TwinGraph({
  stageIndex,
  result = null,
}: TwinGraphProps) {
  /* =======================================================
     BACKEND DATA
     ======================================================= */

  const graph =
    result?.twin_analysis
      ?.graph;

  const provenanceCalls =
    result?.twin_analysis
      ?.provenance?.calls ??
    [];

  const guardrail =
    result?.generated_guardrail ??
    result?.benchmark_report
      ?.guardrail ??
    null;

  /* =======================================================
     EXECUTION ORDER
     ======================================================= */

  const executionOrder =
    useMemo(() => {
      const provenanceOrder =
        unique(
          provenanceCalls.map(
            (call) =>
              call.tool_name,
          ),
        );

      if (
        provenanceOrder.length >
        0
      ) {
        return provenanceOrder;
      }

      if (
        Array.isArray(
          result?.attack_path,
        ) &&
        result.attack_path
          .length > 0
      ) {
        return unique(
          result.attack_path,
        );
      }

      return [];
    }, [
      provenanceCalls,
      result,
    ]);

  /* =======================================================
     BACKEND TOOL NODES
     ======================================================= */

  const backendToolNodes =
    useMemo(() => {
      if (!graph) {
        return [];
      }

      return graph.nodes.filter(
        (node) =>
          node.type === "TOOL",
      );
    }, [graph]);

  const orderedTools =
    useMemo(() => {
      const sourceTools =
        backendToolNodes.length >
        0
          ? backendToolNodes
          : fallbackTools;

      if (
        executionOrder.length ===
        0
      ) {
        return sourceTools;
      }

      return [
        ...sourceTools,
      ].sort((a, b) => {
        const aName =
          getToolName(a);

        const bName =
          getToolName(b);

        const aIndex =
          executionOrder.indexOf(
            aName,
          );

        const bIndex =
          executionOrder.indexOf(
            bName,
          );

        if (
          aIndex === -1 &&
          bIndex === -1
        ) {
          return 0;
        }

        if (aIndex === -1) {
          return 1;
        }

        if (bIndex === -1) {
          return -1;
        }

        return aIndex - bIndex;
      });
    }, [
      backendToolNodes,
      executionOrder,
    ]);

  /* =======================================================
     ATTACK + GUARD STATE
     ======================================================= */

  const attackFound =
    stageIndex >= 1;

  const guarded =
    stageIndex >= 3 &&
    Boolean(
      guardrail?.enabled,
    );

  const externalToolName =
    orderedTools.find(
      isExternalTool,
    );

  const guardedToolName =
    externalToolName
      ? getToolName(
          externalToolName,
        )
      : null;

  /* =======================================================
     REACT FLOW NODES
     ======================================================= */

  const nodes =
    useMemo<Node[]>(() => {
      const agentNode: Node = {
        id: "agent",

        position: {
          x: 40,
          y: 185,
        },

        data: {
          label: (
            <div className="rf-node-content">
              <div className="rf-node-icon">
                <Sparkles
                  size={18}
                />
              </div>

              <span>
                AUTONOMOUS
              </span>

              <strong>
                Agent
              </strong>

              <small>
                execution source
              </small>
            </div>
          ),
        },

        className:
          "rf-node rf-node-agent",
      };

      const toolFlowNodes =
        orderedTools.map(
          (
            tool,
            index,
          ): Node => {
            const name =
              getToolName(tool);

            const isAttackTool =
              attackFound &&
              (
                executionOrder.length ===
                  0 ||
                executionOrder.includes(
                  name,
                )
              );

            const isGuardedTool =
              guarded &&
              name ===
                guardedToolName;

            const relationCount =
              graph?.edges.filter(
                (edge) =>
                  edge.source ===
                    tool.id ||
                  edge.target ===
                    tool.id,
              ).length ?? 0;

            const detail =
              getToolEffect(tool);

            return {
              id: tool.id,

              position:
                getPosition(
                  index,
                ),

              data: {
                label: (
                  <div className="rf-node-content">
                    <div className="rf-node-icon">
                      {renderToolIcon(
                        tool,
                        isGuardedTool,
                      )}
                    </div>

                    <span>
                      {isExternalTool(
                        tool,
                      )
                        ? "EXTERNAL"
                        : "TOOL"}
                    </span>

                    <strong>
                      {name}
                    </strong>

                    <small>
                      {isGuardedTool
                        ? "BLOCKED"
                        : result
                          ? `${detail} · ${tool.risk_level ?? "LOW"}${relationCount > 0 ? ` · ${relationCount} links` : ""}`
                          : detail}
                    </small>
                  </div>
                ),
              },

              className:
                isGuardedTool
                  ? "rf-node rf-node-safe"
                  : isAttackTool
                    ? "rf-node rf-node-risk"
                    : "rf-node rf-node-standard",
            };
          },
        );

      return [
        agentNode,
        ...toolFlowNodes,
      ];
    }, [
      attackFound,
      executionOrder,
      graph,
      guarded,
      guardedToolName,
      orderedTools,
      result,
    ]);

  /* =======================================================
     EXECUTION EDGES

     We use the actual observed provenance order returned by
     the backend to connect the tool nodes.
     ======================================================= */

  const edges =
    useMemo<Edge[]>(() => {
      if (
        orderedTools.length ===
        0
      ) {
        return [];
      }

      const generatedEdges:
        Edge[] = [];

      /* Agent -> first tool */

      generatedEdges.push({
        id: "agent-first-tool",

        source: "agent",

        target:
          orderedTools[0].id,

        animated:
          stageIndex >= 0,

        className:
          "rf-edge rf-edge-normal",
      });

      /* Tool -> tool execution path */

      for (
        let index = 0;
        index <
        orderedTools.length - 1;
        index += 1
      ) {
        const source =
          orderedTools[index];

        const target =
          orderedTools[
            index + 1
          ];

        const targetName =
          getToolName(target);

        const blockedEdge =
          guarded &&
          targetName ===
            guardedToolName;

        generatedEdges.push({
          id: `${source.id}-${target.id}`,

          source:
            source.id,

          target:
            target.id,

          animated:
            attackFound,

          className:
            blockedEdge
              ? "rf-edge rf-edge-blocked"
              : attackFound
                ? "rf-edge rf-edge-risk"
                : "rf-edge rf-edge-normal",
        });
      }

      return generatedEdges;
    }, [
      attackFound,
      guarded,
      guardedToolName,
      orderedTools,
      stageIndex,
    ]);

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <div className="real-twin-graph">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{
          padding: 0.17,
        }}
        minZoom={0.55}
        maxZoom={1.7}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        proOptions={{
          hideAttribution: true,
        }}
      >
        <Background
          gap={28}
          size={1}
          color="rgba(255,255,255,0.035)"
        />

        <Controls
          position="bottom-left"
          showInteractive={false}
        />
      </ReactFlow>

      <div className="twin-graph-legend">
        <span className="legend-normal">
          ● Normal
        </span>

        <span className="legend-risk">
          ● Attack path
        </span>

        <span className="legend-safe">
          ● Guarded
        </span>
      </div>
    </div>
  );
}