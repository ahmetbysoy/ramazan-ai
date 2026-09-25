export function createPlayer(initialState = {}) {
    const state = Object.freeze({
        x: initialState.x ?? 100,
        y: initialState.y ?? 100,
        width: initialState.width ?? 30,
        height: initialState.height ?? 30,
        vx: initialState.vx ?? 0,
        vy: initialState.vy ?? 0,
        gravity: initialState.gravity ?? 0.6,
        jumpStrength: initialState.jumpStrength ?? -10
    });

    return {
        getState() {
            return state;
        },
        update() {
            const newVy = state.vy + state.gravity;
            const newY = state.y + newVy;
            return createPlayer({
                ...state,
                y: newY,
                vy: newVy
            });
        },
        jump() {
            return createPlayer({
                ...state,
                vy: state.jumpStrength
            });
        }
    };
}

export function setupPlayerControls(canvas, getPlayer, setPlayer) {
    const handleJump = (e) => {
        if (e && e.cancelable) {
            e.preventDefault();
        } else if (e) {
            // If not cancelable, still trigger jump without preventDefault
        }
        if (typeof getPlayer === 'function' && typeof setPlayer === 'function') {
            const currentPlayer = getPlayer();
            if (currentPlayer && typeof currentPlayer.jump === 'function') {
                const nextPlayer = currentPlayer.jump();
                setPlayer(nextPlayer);
            }
        }
    };

    canvas.addEventListener('click', handleJump);
    canvas.addEventListener('touchstart', handleJump, { passive: false });

    return () => {
        canvas.removeEventListener('click', handleJump);
        canvas.removeEventListener('touchstart', handleJump);
    };
}
