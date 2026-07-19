import { useEffect, useRef, useState } from 'react';

const TAGLINES = [
  "Evolving theories, one generation at a time.",
  "Mutating ideas in the petri dish of science.",
  "Natural selection at work on your hypotheses.",
  "Cultivating theory organisms...",
  "Running experiments in the primordial soup.",
  "Survival of the fittest hypotheses.",
  "Breeding better answers.",
  "Splicing together novel paradigms.",
  "Observing cellular automata and academic breakthroughs.",
  "Letting the best concepts thrive and multiply.",
  "Simulating the genome of innovation.",
  "Where the strongest models flourish.",
  "Cross-pollinating diverse fields of research.",
  "Watching the ecosystem of knowledge adapt.",
  "Spawning new intellectual lineages.",
  "Applying genetic algorithms to raw curiosity."
];

export function GameOfLife({ useHighLifeRules = false }: { useHighLifeRules?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [taglineIndex, setTaglineIndex] = useState(0);

  useEffect(() => {
    // Pick an initial random tagline on mount
    setTaglineIndex(Math.floor(Math.random() * TAGLINES.length));

    const textInterval = setInterval(() => {
      setTaglineIndex((prev) => {
        let next;
        do {
          next = Math.floor(Math.random() * TAGLINES.length);
        } while (next === prev); // Ensure it actually changes
        return next;
      });
    }, 10000);

    return () => {
      clearInterval(textInterval);
    };
  }, []);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let lastTime = 0;
    const fps = 6; // Half of previous speed (12 -> 6)
    const interval = 1000 / fps;

    const cellSize = 14;
    let cols = 0;
    let rows = 0;
    let grid: number[][] = [];
    let history: string[] = [];
    let stagnationCounter = 0;

    const initGrid = () => {
      grid = new Array(cols).fill(null).map(() =>
        new Array(rows).fill(null).map(() => (Math.random() > 0.85 ? 1 : 0))
      );
      history = [];
      stagnationCounter = 0;
    };

    const resize = () => {
      const parent = canvas.parentElement;
      if (parent) {
        canvas.width = parent.clientWidth;
        canvas.height = parent.clientHeight;
        cols = Math.floor(canvas.width / cellSize);
        rows = Math.floor(canvas.height / cellSize);
        initGrid();
      }
    };

    window.addEventListener('resize', resize);
    resize();

    const updateGrid = () => {
      const newGrid = grid.map(arr => [...arr]);
      let aliveCount = 0;

      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          let neighbors = 0;
          for (let x = -1; x <= 1; x++) {
            for (let y = -1; y <= 1; y++) {
              if (x === 0 && y === 0) continue;
              const col = (i + x + cols) % cols;
              const row = (j + y + rows) % rows;
              neighbors += grid[col][row];
            }
          }
          if (grid[i][j] === 1 && (neighbors < 2 || neighbors > 3)) {
            newGrid[i][j] = 0;
          } else if (grid[i][j] === 0 && (neighbors === 3 || (useHighLifeRules && neighbors === 6))) {
            newGrid[i][j] = 1;
          }
          aliveCount += newGrid[i][j];
        }
      }
      grid = newGrid;

      // Stagnation detection
      const stateHash = grid.map(col => col.reduce((a, b) => a + b, 0)).join(',');
      history.push(stateHash);
      if (history.length > 20) history.shift();

      if (history.length === 20) {
        const uniqueStates = new Set(history).size;
        if (uniqueStates <= 4) {
          stagnationCounter++;
        } else {
          stagnationCounter = 0;
        }
      }

      if (aliveCount === 0 || stagnationCounter > 15) {
        initGrid();
      }
    };

    const draw = () => {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          if (grid[i][j] === 1) {
            // Brighter active cell: a noticeable gray instead of stark black
            ctx.fillStyle = '#6b7280';
            ctx.fillRect(i * cellSize + 1, j * cellSize + 1, cellSize - 2, cellSize - 2);
          } else {
            ctx.fillStyle = '#f3f4f6';
            ctx.fillRect(i * cellSize + cellSize / 2 - 1, j * cellSize + cellSize / 2 - 1, 2, 2);
          }
        }
      }
    };

    const loop = (time: number) => {
      animationFrameId = requestAnimationFrame(loop);
      const deltaTime = time - lastTime;
      if (deltaTime >= interval) {
        lastTime = time - (deltaTime % interval);
        updateGrid();
        draw();
      }
    };

    animationFrameId = requestAnimationFrame(loop);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [useHighLifeRules]);

  return (
    <div className="flex-1 w-full h-full relative overflow-hidden flex flex-col items-center justify-center bg-white">
      <canvas ref={canvasRef} className="absolute inset-0 z-0 opacity-[0.15]" />
      <div className="z-10 bg-white/90 p-10 border-2 border-black backdrop-blur-sm text-center shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] flex flex-col items-center max-w-sm transition-all">
        <h2 className="text-3xl font-black tracking-tighter mb-3">Researching</h2>
        <p className="text-gray-500 text-sm font-bold tracking-widest leading-relaxed transition-opacity duration-500 min-h-[3rem] flex items-center justify-center">
          {TAGLINES[taglineIndex]}
        </p>
      </div>
    </div>
  );
}