import express,{ Request, Response } from "express";

import dotenv from 'dotenv'

dotenv.config(); 
const app = express();
const PORT  = process.env.PORT || 3001;


app.use(express.json())

app.get("/", (req: Request, res: Response) => {
    res.send("GitGoblin! is awake and hungry for some code to review Kaboom!!");
});

app.post('/webhook', (req: Request, res: Response) => {
    const payload = req.body;
    
    // Check if this is a Pull Request event
    if (payload.action === 'opened' || payload.action === 'synchronize') {
        const prNumber = payload.pull_request.number;
        const repoName = payload.repository.full_name;
        
        console.log(`[gitGoblin] Alert! New changes in ${repoName} (PR #${prNumber})`);
        
        // This is where the ReAct Agent logic will be triggered
    }

    res.status(200).send('Event Received');
})
app.listen(PORT, () => {
    console.log(`Example app listening on port ${PORT}`);
});