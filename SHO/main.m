clear all 
clc
SearchAgents=30; 
Fun_name='F1';  
Max_iterations=1000; 
[lowerbound,upperbound,dimension,fitness]=fun_info(Fun_name);
[Best_score,Best_pos,SHO_curve]=sho(SearchAgents,Max_iterations,lowerbound,upperbound,dimension,fitness);
figure('Position',[500 500 300 300])
plots=semilogx(SHO_curve,'Color','g');
set(plots,'linewidth',2)
hold on
title('Objective space')
xlabel('Iterations');
ylabel('Best fitness score');
axis tight
grid on
box on
legend('SHO')
display(['The best optimal value of the objective function found by SHO is : ', num2str(Best_score)]);

        



